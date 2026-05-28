"""Service layer for formatting chat responses as Server-Sent Events."""

import json
import logging
import time

logger = logging.getLogger(__name__)


def _sse(event: dict) -> str:
    """Serialize one event payload using the SSE data format."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _doc_to_dict(doc, index: int) -> dict:
    metadata = getattr(doc, "metadata", {}) or {}
    return {
        "index": index,
        "title": metadata.get("title", ""),
        "source": metadata.get("source", ""),
        "brand": metadata.get("brand", ""),
        "rerank_score": metadata.get("rerank_score"),
        "page_content": getattr(doc, "page_content", ""),
    }


def _persist_log(
    *,
    user,
    session_id: str,
    query: str,
    history: str,
    result: dict,
    latency_ms: int,
):
    """Save a ChatLog row + run inline groundedness scoring. Best-effort."""
    try:
        from django.db import close_old_connections

        from manager.models import ChatLog
        from rag_engine.core.config import settings as rag_settings
        from rag_engine.rag.tools import score_answer

        close_old_connections()

        answer = result.get("answer", "") or ""
        context = result.get("context", "") or ""
        docs = result.get("retrieved_docs", []) or []

        groundedness = None
        flag = ChatLog.FLAG_UNCHECKED
        if rag_settings.reranker_enabled and answer and context:
            try:
                groundedness = score_answer(answer, context)
                if groundedness is not None:
                    flag = (
                        ChatLog.FLAG_OK
                        if groundedness >= rag_settings.hallucination_threshold
                        else ChatLog.FLAG_SUSPICIOUS
                    )
            except Exception:
                logger.exception("Groundedness scoring failed.")

        ChatLog.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            session_id=session_id or "",
            query=query,
            answer=answer,
            context_used=context,
            retrieved_docs=[_doc_to_dict(doc, idx) for idx, doc in enumerate(docs)],
            sources=result.get("sources", []) or [],
            latency_ms=latency_ms,
            top_k=rag_settings.rag_top_k,
            model_name=rag_settings.llm_model,
            error=result.get("error") or "",
            groundedness_score=groundedness,
            hallucination_flag=flag,
        )
    except Exception:
        logger.exception("Failed to persist ChatLog.")


def stream_chat(query: str, history: str = "", user=None, session_id: str = ""):
    """Yield SSE events for one chat request.

    The RAG engine owns classification, retrieval, prompting, generation, and
    guardrails. This Django service only adapts the engine result to the SSE
    response format expected by the view/frontend, and persists a ChatLog row
    for hallucination review.
    """
    started = time.monotonic()
    try:
        from rag_engine.rag.pipeline import ask

        result = ask(query, history=history)
    except Exception as exc:
        logger.exception("Chat request failed.")
        latency_ms = int((time.monotonic() - started) * 1000)
        _persist_log(
            user=user,
            session_id=session_id,
            query=query,
            history=history,
            result={"answer": "", "error": str(exc), "sources": []},
            latency_ms=latency_ms,
        )
        yield _sse({"error": str(exc)})
        yield _sse({"done": True, "sources": []})
        return

    latency_ms = int((time.monotonic() - started) * 1000)
    sources = result.get("sources", [])
    error = result.get("error")
    answer = result.get("answer", "")

    yield _sse({"sources": sources})

    if error:
        yield _sse({"error": error})

    if answer:
        yield _sse({"token": answer})

    yield _sse({"done": True, "sources": sources})

    _persist_log(
        user=user,
        session_id=session_id,
        query=query,
        history=history,
        result=result,
        latency_ms=latency_ms,
    )
