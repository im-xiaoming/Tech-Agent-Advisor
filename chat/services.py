"""Service layer for formatting chat responses as Server-Sent Events."""

import json
import logging

logger = logging.getLogger(__name__)


def _sse(event: dict) -> str:
    """Serialize one event payload using the SSE data format."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def stream_chat(query: str, history: str = ""):
    """Yield SSE events for one chat request.

    The RAG engine owns classification, retrieval, prompting, generation, and
    guardrails. This Django service only adapts the engine result to the SSE
    response format expected by the view/frontend.
    """
    try:
        from rag_engine.rag.pipeline import ask

        result = ask(query, history=history)
    except Exception as exc:
        logger.exception("Chat request failed.")
        yield _sse({"error": str(exc)})
        yield _sse({"done": True, "sources": []})
        return

    sources = result.get("sources", [])
    error = result.get("error")
    answer = result.get("answer", "")

    yield _sse({"sources": sources})

    if error:
        yield _sse({"error": error})

    if answer:
        yield _sse({"token": answer})

    yield _sse({"done": True, "sources": sources})
