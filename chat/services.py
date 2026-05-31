"""Service layer for formatting chat responses as Server-Sent Events."""

import json
import logging
import threading
import time

logger = logging.getLogger(__name__)


# Distinctive prompt scaffolding that essentially never shows up in a genuine
# product answer. Any single one of these is strong evidence of a leak.
_STRONG_LEAK_MARKERS = (
    "system prompt",
    "output requirements",
    "=== context",
    "hết context",
    "hướng dẫn cho lượt trả lời",
    "{context}",
    "{history}",
    "{query}",
    "{extra_instructions}",
)
# Weaker markers: common enough in normal prose that one alone is not proof;
# require at least two distinct hits before treating it as a leak.
_WEAK_LEAK_MARKERS = (
    "question:",
    "trả lời:",
    "yêu cầu:",
)
_PROMPT_LEAK_FALLBACK = (
    "Mình chưa có đủ dữ liệu trong kho để trả lời chính xác. "
    "Bạn có thể cho mình thêm nhu cầu như loại sản phẩm, ngân sách hoặc hãng ưu tiên không?"
)


def _looks_like_prompt_leak(text: str) -> bool:
    normalized = text.lower()
    if any(marker in normalized for marker in _STRONG_LEAK_MARKERS):
        return True
    weak_hits = sum(1 for marker in _WEAK_LEAK_MARKERS if marker in normalized)
    return weak_hits >= 5


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
        is_fallback = result.get("error") in {"No retrieved context.", "Unable to classify intent.", "Query is empty."}

        groundedness = None
        flag = ChatLog.FLAG_UNCHECKED
        if rag_settings.reranker_enabled and answer and context and not is_fallback:
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
    """Yield SSE events for one chat request, streaming LLM tokens in real time."""
    started = time.monotonic()
    final_state: dict = {}
    full_answer = ""
    streamed_sources: list = []
    error: str | None = None
    pending_tokens: list[str] = []
    prompt_leak_blocked = False

    try:
        from rag_engine.rag.pipeline import ask_stream

        for event in ask_stream(query, history=history):
            if "status" in event:
                # Progress hint for the UI (e.g. "searching_documents"). Stateless.
                yield _sse({"status": event["status"]})
            elif "sources" in event and "token" not in event and "final" not in event:
                streamed_sources = event["sources"] or []
                yield _sse({"sources": streamed_sources})
            elif "regenerating" in event:
                # Tell the UI to discard the partial answer and start fresh.
                full_answer = ""
                yield _sse({"regenerating": True, "reason": event.get("reason", "")})
            elif "low_confidence" in event:
                yield _sse({
                    "low_confidence": True,
                    "groundedness": event.get("groundedness"),
                })
            elif "token" in event:
                token = event["token"]
                if not token:
                    continue
                full_answer += token
                if _looks_like_prompt_leak(full_answer):
                    prompt_leak_blocked = True
                    full_answer = _PROMPT_LEAK_FALLBACK
                    final_state = {
                        **final_state,
                        "answer": full_answer,
                        "sources": streamed_sources,
                        "error": "Prompt leak blocked.",
                    }
                    yield _sse({"regenerating": True, "reason": "prompt_leak_blocked"})
                    yield _sse({"token": full_answer})
                    break

                if pending_tokens is not None:
                    pending_tokens.append(token)
                    if len("".join(pending_tokens)) < 160:
                        continue
                    yield _sse({"token": "".join(pending_tokens)})
                    pending_tokens = None
                else:
                    yield _sse({"token": token})
            elif "final" in event:
                final_state = event["final"] or {}
        if pending_tokens and not prompt_leak_blocked:
            yield _sse({"token": "".join(pending_tokens)})
    except Exception as exc:
        logger.exception("Chat request failed.")
        error = str(exc)
        yield _sse({"error": error})

    sources = final_state.get("sources") or streamed_sources or []
    err = final_state.get("error") or error
    if err:
        yield _sse({"error": err})

    yield _sse({"done": True, "sources": sources})

    latency_ms = int((time.monotonic() - started) * 1000)
    log_payload = {
        "answer": final_state.get("answer", full_answer),
        "context": final_state.get("context", ""),
        "retrieved_docs": final_state.get("retrieved_docs", []),
        "sources": sources,
        "error": err or "",
    }
    # Fire-and-forget so groundedness scoring (cross-encoder forward pass) does
    # not block the SSE response from closing.
    threading.Thread(
        target=_persist_log,
        kwargs={
            "user": user,
            "session_id": session_id,
            "query": query,
            "history": history,
            "result": log_payload,
            "latency_ms": latency_ms,
        },
        daemon=True,
    ).start()
