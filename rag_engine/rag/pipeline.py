"""API cấp cao để hỏi chatbot RAG từ code Django hoặc CLI."""

from functools import lru_cache

from rag_engine.agents.advisor.agent import (
    stream_advisor_tokens,
    stream_smalltalk_tokens,
)
from rag_engine.agents.graph import build_chat_graph
from rag_engine.agents.guardrails.agent import no_context_guardrail_agent
from rag_engine.agents.retrieval.agent import make_retrieval_agent
from rag_engine.agents.supervisor.agent import supervisor_agent
from rag_engine.core.config import settings
from rag_engine.rag.tools import score_answer, verify_citations
from rag_engine.rag.vector_store import load_vector_db


_REGEN_INSTRUCTIONS = (
    "LƯU Ý LẦN VIẾT LẠI: lượt trước câu trả lời chưa đủ căn cứ từ CONTEXT. "
    "Lần này hãy bám sát NGUYÊN VĂN thông số trong CONTEXT, BẮT BUỘC kèm [N] cho mọi câu chứa thông tin sản phẩm, "
    "và KHÔNG suy luận ngoài CONTEXT. Nếu CONTEXT không đủ, nói thẳng phần thiếu."
)


def _evaluate_answer(answer: str, context: str, num_docs: int) -> dict:
    """Run citation + groundedness checks. Returns a verdict dict."""
    citation_report = verify_citations(answer, num_docs)
    groundedness = None
    if settings.reranker_enabled and answer and context:
        try:
            groundedness = score_answer(answer, context)
        except Exception:
            groundedness = None

    needs_regen = False
    reasons = []
    if not citation_report["ok"]:
        needs_regen = True
        if citation_report["invalid"]:
            reasons.append(f"invalid citations: {citation_report['invalid']}")
        if citation_report["missing"]:
            reasons.append("missing citations")
    if (
        groundedness is not None
        and groundedness < settings.regenerate_threshold
    ):
        needs_regen = True
        reasons.append(f"groundedness {groundedness:.2f} < {settings.regenerate_threshold}")

    return {
        "citation_report": citation_report,
        "groundedness": groundedness,
        "needs_regen": needs_regen,
        "reasons": reasons,
    }


@lru_cache(maxsize=1)
def get_default_db():
    """Load the configured Qdrant collection and cache it for later queries."""
    return load_vector_db()


@lru_cache(maxsize=1)
def get_default_graph():
    """Build and cache the default chat graph."""
    vector_db = get_default_db()
    return build_chat_graph(vector_db, top_k=settings.rag_top_k)


def ask(query: str, history: str, db=None, temperature: float | None = None, top_k: int | None = None) -> dict:
    vector_db = db or get_default_db()
    graph = get_default_graph()
    
    result = graph.invoke(
        {
            "query": query,
            "history": history,
            "temperature": temperature if temperature is not None else settings.rag_temperature,
            "top_k": top_k or settings.rag_top_k,
        }
    )
    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "error": result.get("error"),
        "retrieved_docs": result.get("retrieved_docs", []),
        "context": result.get("context", ""),
        "route": result.get("route", ""),
    }


@lru_cache(maxsize=1)
def _get_retrieval_agent():
    """Cached retrieval agent bound to the default vector DB."""
    return make_retrieval_agent(get_default_db(), settings.rag_top_k)


def ask_stream(
    query: str,
    history: str,
    db=None,
    temperature: float | None = None,
    top_k: int | None = None,
):
    """Generator orchestrating the chat pipeline with real token streaming.

    Yields event dicts:
      - ``{"sources": [...]}`` once retrieval finishes
      - ``{"token": "..."}`` for each LLM chunk
      - ``{"final": {...full state...}}`` exactly once at the end
    """
    state = {
        "query": query,
        "history": history,
        "temperature": temperature if temperature is not None else settings.rag_temperature,
        "top_k": top_k or settings.rag_top_k,
    }

    state = supervisor_agent(state)
    route = state.get("route")

    if route in ("invalid",) or (route == "smalltalk" and not state.get("query")):
        answer = state.get("answer", "")
        yield {"sources": []}
        if answer:
            yield {"token": answer}
        yield {"final": {**state, "answer": answer, "sources": []}}
        return

    if route == "smalltalk":
        yield {"sources": []}
        full = ""
        for chunk in stream_smalltalk_tokens(state):
            full += chunk
            yield {"token": chunk}
        yield {"final": {**state, "answer": full, "sources": []}}
        return

    # product_advice
    retrieval = _get_retrieval_agent() if db is None else make_retrieval_agent(db, settings.rag_top_k)
    state = retrieval(state)

    if not state.get("retrieved_docs"):
        state = no_context_guardrail_agent(state)
        yield {"sources": []}
        yield {"token": state.get("answer", "")}
        yield {"final": state}
        return

    yield {"sources": state.get("sources", [])}

    full = ""
    for chunk in stream_advisor_tokens(state):
        full += chunk
        yield {"token": chunk}

    # Post-generation verification + optional regenerate-on-fail.
    num_docs = len(state.get("retrieved_docs", []))
    verdict = _evaluate_answer(full, state.get("context", ""), num_docs)
    low_confidence = not verdict["citation_report"]["ok"] or (
        verdict["groundedness"] is not None
        and verdict["groundedness"] < settings.hallucination_threshold
    )

    if settings.regenerate_enabled and verdict["needs_regen"]:
        for attempt in range(settings.max_regenerations):
            yield {"regenerating": True, "reason": "; ".join(verdict["reasons"])}
            full = ""
            for chunk in stream_advisor_tokens(state, extra_instructions=_REGEN_INSTRUCTIONS):
                full += chunk
                yield {"token": chunk}
            verdict = _evaluate_answer(full, state.get("context", ""), num_docs)
            low_confidence = not verdict["citation_report"]["ok"] or (
                verdict["groundedness"] is not None
                and verdict["groundedness"] < settings.hallucination_threshold
            )
            if not verdict["needs_regen"]:
                break

    if low_confidence:
        yield {
            "low_confidence": True,
            "groundedness": verdict["groundedness"],
            "citation_issues": verdict["citation_report"],
        }

    yield {
        "final": {
            **state,
            "answer": full,
            "low_confidence": low_confidence,
            "groundedness_inline": verdict["groundedness"],
        }
    }