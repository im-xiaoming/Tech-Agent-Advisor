"""Background RAGAS evaluation for chat answers.

The public entry point is :func:`evaluate_chatlog_async`, which snapshots a
``ChatLog`` into a :class:`~evaluation.models.RagEvaluation` row and scores it on
a **daemon thread**. Nothing here ever runs on the request/SSE path, so chat
latency is unaffected.

Scoring uses the RAGAS 0.4 "collections" metric classes. Each metric makes its
own LLM call (and ``answer_relevancy`` also needs embeddings), so a full run is
several OpenAI calls — that is precisely why it is pushed off-thread.
"""

import logging
import math
import random
import threading
import time

logger = logging.getLogger(__name__)

# Default judge model. Must be a NON-reasoning model: reasoning models (e.g.
# gpt-5-mini) spend their whole token budget on hidden reasoning and return
# empty content (finish_reason="length"), so instructor can't parse the
# structured output RAGAS needs and every metric ends up blank.
DEFAULT_JUDGE_MODEL = "gpt-4.1-mini"


def _eval_config() -> dict:
    """Read evaluation toggles from Django settings with safe defaults."""
    from django.conf import settings as dj

    return {
        "enabled": bool(getattr(dj, "RAG_EVALUATION_ENABLED", True)),
        "sample_rate": float(getattr(dj, "RAG_EVALUATION_SAMPLE_RATE", 1.0)),
        "llm_model": getattr(dj, "RAG_EVALUATION_LLM_MODEL", "") or None,
        "embedding_model": getattr(
            dj, "RAG_EVALUATION_EMBEDDING_MODEL", "text-embedding-3-small"
        ),
        "max_tokens": int(getattr(dj, "RAG_EVALUATION_MAX_TOKENS", 8192)),
    }


def _build_judges(llm_model: str | None):
    """Construct the RAGAS judge LLM + embeddings backed by an async OpenAI client.

    ``.score()`` internally calls ``asyncio.run(.ascore())``, which requires an
    *async* client, so we use ``AsyncOpenAI``. A fresh client is built per run to
    avoid sharing an httpx pool across event loops/threads.
    """
    from openai import AsyncOpenAI
    from ragas.embeddings import OpenAIEmbeddings
    from ragas.llms import llm_factory

    from rag_engine.core.config import settings as rag

    api_key = rag.openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for RAGAS evaluation.")

    model = llm_model or DEFAULT_JUDGE_MODEL
    cfg = _eval_config()
    client = AsyncOpenAI(api_key=api_key)
    # Faithfulness echoes every atomic statement + reason as JSON; a rich product
    # answer easily blows past the default token cap (finish_reason="length"),
    # so give the judge generous headroom.
    judge_llm = llm_factory(
        model, provider="openai", client=client, max_tokens=cfg["max_tokens"]
    )
    judge_emb = OpenAIEmbeddings(client=client, model=cfg["embedding_model"])
    return judge_llm, judge_emb, model


def _metric_value(result) -> float | None:
    value = getattr(result, "value", None)
    try:
        number = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    # RAGAS returns NaN when a metric is undefined for the sample (e.g.
    # faithfulness on an answer with no factual statements). Store it as None
    # so it reads as "missing" and doesn't poison the average.
    if number is not None and math.isnan(number):
        return None
    return number


def _compute_metrics(judge_llm, judge_emb, *, question, answer, contexts, ground_truth):
    """Score one answer; each metric is isolated so one failure isn't fatal."""
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecisionWithoutReference,
        ContextRecall,
        Faithfulness,
    )

    scores: dict[str, float | None] = {}

    try:
        scores["faithfulness"] = _metric_value(
            Faithfulness(llm=judge_llm).score(
                user_input=question,
                response=answer,
                retrieved_contexts=contexts,
            )
        )
    except Exception:
        logger.exception("RAGAS faithfulness failed.")

    try:
        scores["answer_relevancy"] = _metric_value(
            AnswerRelevancy(llm=judge_llm, embeddings=judge_emb).score(
                user_input=question,
                response=answer,
            )
        )
    except Exception:
        logger.exception("RAGAS answer_relevancy failed.")

    try:
        scores["context_precision"] = _metric_value(
            ContextPrecisionWithoutReference(llm=judge_llm).score(
                user_input=question,
                response=answer,
                retrieved_contexts=contexts,
            )
        )
    except Exception:
        logger.exception("RAGAS context_precision failed.")

    # context_recall needs a gold reference; skip when absent.
    if ground_truth:
        try:
            scores["context_recall"] = _metric_value(
                ContextRecall(llm=judge_llm).score(
                    user_input=question,
                    retrieved_contexts=contexts,
                    reference=ground_truth,
                )
            )
        except Exception:
            logger.exception("RAGAS context_recall failed.")

    return scores


def run_evaluation(eval_id: int) -> None:
    """Score a single :class:`RagEvaluation` row. Safe to call from any thread."""
    from django.db import close_old_connections

    from evaluation.models import RagEvaluation

    close_old_connections()
    try:
        evaluation = RagEvaluation.objects.get(pk=eval_id)
    except RagEvaluation.DoesNotExist:
        return

    evaluation.status = RagEvaluation.STATUS_RUNNING
    evaluation.save(update_fields=["status", "updated_at"])

    started = time.monotonic()
    try:
        cfg = _eval_config()
        judge_llm, judge_emb, model = _build_judges(cfg["llm_model"])
        scores = _compute_metrics(
            judge_llm,
            judge_emb,
            question=evaluation.question,
            answer=evaluation.answer,
            contexts=evaluation.contexts or [],
            ground_truth=evaluation.ground_truth or "",
        )
        evaluation.faithfulness = scores.get("faithfulness")
        evaluation.answer_relevancy = scores.get("answer_relevancy")
        evaluation.context_precision = scores.get("context_precision")
        evaluation.context_recall = scores.get("context_recall")
        evaluation.model_name = model
        evaluation.error = ""
        evaluation.status = RagEvaluation.STATUS_DONE
    except Exception as exc:
        logger.exception("RAGAS evaluation failed for eval #%s.", eval_id)
        evaluation.error = str(exc)
        evaluation.status = RagEvaluation.STATUS_FAILED
    finally:
        evaluation.latency_ms = int((time.monotonic() - started) * 1000)
        evaluation.save()
        close_old_connections()


def run_evaluation_async(eval_id: int) -> None:
    """Run :func:`run_evaluation` on a daemon thread (used by admin re-runs)."""
    threading.Thread(target=run_evaluation, args=(eval_id,), daemon=True).start()


def _contexts_from_chatlog(chat_log) -> list[str]:
    """Extract retrieved-context strings from a ChatLog for RAGAS."""
    contexts: list[str] = []
    for doc in chat_log.retrieved_docs or []:
        if isinstance(doc, dict):
            text = (doc.get("page_content") or "").strip()
            if text:
                contexts.append(text)
    if not contexts and chat_log.context_used:
        contexts = [chat_log.context_used]
    return contexts


def evaluate_chatlog_async(chat_log):
    """Create a pending evaluation for ``chat_log`` and score it off-thread.

    Returns the created :class:`RagEvaluation`, or ``None`` when skipped
    (disabled, sampled out, or nothing meaningful to score).
    """
    cfg = _eval_config()
    if not cfg["enabled"]:
        return None
    if cfg["sample_rate"] < 1.0 and random.random() > cfg["sample_rate"]:
        return None

    answer = (chat_log.answer or "").strip()
    contexts = _contexts_from_chatlog(chat_log)
    # Only grounded product answers are worth scoring — skip fallbacks/errors.
    if not answer or not contexts or chat_log.error:
        return None

    from evaluation.models import RagEvaluation

    evaluation = RagEvaluation.objects.create(
        chat_log=chat_log,
        question=chat_log.query,
        answer=answer,
        contexts=contexts,
        status=RagEvaluation.STATUS_PENDING,
    )
    run_evaluation_async(evaluation.pk)
    return evaluation
