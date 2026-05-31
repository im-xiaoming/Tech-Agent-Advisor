"""Streaming orchestration helpers for the RAG chat pipeline."""

import logging
import time
from collections.abc import Callable, Iterable

from rag_engine.agents.advisor.agent import (
    stream_advisor_tokens,
    stream_smalltalk_tokens,
)
from rag_engine.agents.guardrails.agent import no_context_guardrail_agent
from rag_engine.agents.retrieval.agent import make_retrieval_agent
from rag_engine.agents.supervisor.agent import supervisor_agent
from rag_engine.core.config import settings
from rag_engine.rag.semantic_cache import get_cached_answer, save_answer_cache_async
from rag_engine.rag.tools import score_answer, verify_citations


logger = logging.getLogger(__name__)

_REGEN_INSTRUCTIONS = (
    "LƯU Ý LẦN VIẾT LẠI: lượt trước câu trả lời chưa đủ căn cứ từ CONTEXT. "
    "Lần này hãy bám sát NGUYÊN VĂN thông số trong CONTEXT. "
    "BẮT BUỘC dùng citation số thật như [1], [2] cho mọi câu chứa thông tin sản phẩm. "
    "Tuyệt đối không in chữ N trong ngoặc vuông. Nếu CONTEXT không đủ, nói thẳng phần thiếu."
)


def _log_timing(step: str, started: float, **fields) -> None:
    """Log elapsed milliseconds for a named RAG pipeline step."""
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    details = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.warning(
        "RAG timing step=%s ms=%s%s",
        step,
        elapsed_ms,
        f" {details}" if details else "",
    )


def _build_initial_state(
    query: str,
    history: str,
    temperature: float | None,
    top_k: int | None,
) -> dict:
    """Create the initial AgentState payload for a chat turn."""
    return {
        "query": query,
        "history": history,
        "temperature": temperature if temperature is not None else settings.rag_temperature,
        "top_k": top_k or settings.rag_top_k,
    }


def _route_with_supervisor(state: dict, original_query: str) -> tuple[dict, str]:
    """Run the supervisor and log its route decision timing."""
    step_started = time.perf_counter()
    state = supervisor_agent(state)
    route = state.get("route")
    _log_timing(
        "supervisor",
        step_started,
        route=route,
        query_len=len(original_query or ""),
        rewritten_len=len(state.get("query", "") or ""),
    )
    return state, route


def _evaluate_answer(answer: str, context: str, num_docs: int) -> dict:
    """Run citation + groundedness checks and return a verdict dict."""
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
        if citation_report.get("placeholder"):
            reasons.append("placeholder citation")
        if citation_report["missing"]:
            reasons.append("missing citations")
    if groundedness is not None and groundedness < settings.regenerate_threshold:
        needs_regen = True
        reasons.append(f"groundedness {groundedness:.2f} < {settings.regenerate_threshold}")

    return {
        "citation_report": citation_report,
        "groundedness": groundedness,
        "needs_regen": needs_regen,
        "reasons": reasons,
    }


def _is_low_confidence(verdict: dict) -> bool:
    """Return whether the answer verdict should be marked low confidence."""
    return not verdict["citation_report"]["ok"] or (
        verdict["groundedness"] is not None
        and verdict["groundedness"] < settings.hallucination_threshold
    )


def _stream_terminal_response(
    state: dict,
    total_started: float,
    route: str,
    answer: str,
    sources: list | None = None,
    **final_fields,
):
    """Yield a short terminal response and final state for non-RAG branches."""
    sources = sources or []
    yield {"sources": sources}
    if answer:
        yield {"token": answer}
    yield {"final": {**state, "answer": answer, "sources": sources, **final_fields}}
    _log_timing("total", total_started, route=route, docs=0, chars=len(answer or ""))


def _stream_smalltalk_response(state: dict, total_started: float, route: str):
    """Stream smalltalk model chunks and emit the final smalltalk state."""
    yield {"sources": []}
    full = yield from _stream_answer_tokens(
        stream_smalltalk_tokens(state),
        first_token_step="smalltalk_first_token",
        generation_step="smalltalk_generation",
    )
    yield {"final": {**state, "answer": full, "sources": []}}
    _log_timing("total", total_started, route=route, chars=len(full))


def _lookup_semantic_cache(state: dict) -> dict | None:
    """Look up a cached semantic answer for the rewritten query and filters."""
    step_started = time.perf_counter()
    cached = get_cached_answer(state.get("query", ""), state.get("filters") or {})
    _log_timing(
        "semantic_cache_lookup",
        step_started,
        hit=bool(cached),
        threshold=settings.semantic_cache_threshold,
    )
    return cached


def _stream_cached_response(state: dict, cached: dict, total_started: float, route: str):
    """Yield a semantic-cache hit response and skip retrieval/generation."""
    answer = cached.get("answer", "")
    sources = cached.get("sources", []) or []
    yield {"sources": sources}
    yield {"token": answer}
    yield {
        "final": {
            **state,
            "answer": answer,
            "sources": sources,
            "retrieved_docs": [],
            "context": "",
            "cache_hit": True,
            "cache_similarity": cached.get("similarity"),
            "cache_entry_id": cached.get("entry_id"),
        }
    }
    _log_timing(
        "total",
        total_started,
        route=route,
        docs=0,
        chars=len(answer),
        cache_hit=True,
    )


def _select_retrieval_agent(db, get_default_retrieval_agent: Callable):
    """Return a retrieval agent bound to either the provided DB or default DB."""
    if db is None:
        return get_default_retrieval_agent()
    return make_retrieval_agent(db, settings.rag_top_k)


def _run_retrieval(state: dict, db, get_default_retrieval_agent: Callable) -> tuple[dict, list]:
    """Run retrieval and log document count, filter use, and reranker status."""
    step_started = time.perf_counter()
    retrieval = _select_retrieval_agent(db, get_default_retrieval_agent)
    state = retrieval(state)
    docs = state.get("retrieved_docs") or []
    _log_timing(
        "retrieval",
        step_started,
        docs=len(docs),
        filters=bool(state.get("filters")),
        reranker=settings.reranker_enabled,
    )
    return state, docs


def _stream_no_context_response(state: dict, total_started: float, route: str):
    """Run the no-context guardrail and emit its fallback answer."""
    step_started = time.perf_counter()
    state = no_context_guardrail_agent(state)
    _log_timing("no_context_guardrail", step_started)
    yield from _stream_terminal_response(
        state,
        total_started,
        route,
        state.get("answer", ""),
    )


def _stream_answer_tokens(
    chunks: Iterable[str],
    *,
    first_token_step: str,
    generation_step: str,
    **timing_fields,
) -> str:
    """Yield token events from an LLM stream and return the full answer."""
    full = ""
    step_started = time.perf_counter()
    first_token_logged = False
    for chunk in chunks:
        if not first_token_logged:
            _log_timing(first_token_step, step_started, **timing_fields)
            first_token_logged = True
        full += chunk
        yield {"token": chunk}
    _log_timing(generation_step, step_started, chars=len(full), **timing_fields)
    return full


def _evaluate_answer_phase(full: str, state: dict, num_docs: int) -> tuple[dict, bool]:
    """Evaluate the generated answer and log citation/groundedness timing."""
    step_started = time.perf_counter()
    verdict = _evaluate_answer(full, state.get("context", ""), num_docs)
    _log_timing(
        "evaluate",
        step_started,
        groundedness=verdict["groundedness"],
        needs_regen=verdict["needs_regen"],
        citation_ok=verdict["citation_report"]["ok"],
    )
    return verdict, _is_low_confidence(verdict)


def _evaluate_regenerated_answer(full: str, state: dict, num_docs: int, attempt: int) -> tuple[dict, bool]:
    """Evaluate a regenerated answer and log its verification timing."""
    step_started = time.perf_counter()
    verdict = _evaluate_answer(full, state.get("context", ""), num_docs)
    _log_timing(
        "regenerate_evaluate",
        step_started,
        attempt=attempt,
        groundedness=verdict["groundedness"],
        needs_regen=verdict["needs_regen"],
        citation_ok=verdict["citation_report"]["ok"],
    )
    return verdict, _is_low_confidence(verdict)


def _stream_regenerations(state: dict, full: str, verdict: dict, low_confidence: bool, num_docs: int):
    """Regenerate an answer when verification fails and return the final verdict."""
    if not settings.regenerate_enabled or not verdict["needs_regen"]:
        return full, verdict, low_confidence

    for attempt in range(1, settings.max_regenerations + 1):
        yield {"regenerating": True, "reason": "; ".join(verdict["reasons"])}
        full = yield from _stream_answer_tokens(
            stream_advisor_tokens(state, extra_instructions=_REGEN_INSTRUCTIONS),
            first_token_step="regenerate_first_token",
            generation_step="regenerate_generation",
            attempt=attempt,
        )
        verdict, low_confidence = _evaluate_regenerated_answer(
            full,
            state,
            num_docs,
            attempt,
        )
        if not verdict["needs_regen"]:
            break
    return full, verdict, low_confidence


def _stream_low_confidence_warning(verdict: dict, low_confidence: bool):
    """Yield a low-confidence event when verification flags the answer."""
    if low_confidence:
        yield {
            "low_confidence": True,
            "groundedness": verdict["groundedness"],
            "citation_issues": verdict["citation_report"],
        }


def _save_semantic_cache_if_eligible(state: dict, full: str, low_confidence: bool) -> None:
    """Persist a successful answer to semantic cache in the background."""
    if low_confidence or not full:
        return
    save_answer_cache_async(
        question=state.get("query", ""),
        answer=full,
        sources=state.get("sources", []) or [],
        filters=state.get("filters") or {},
        model_name=settings.llm_model,
    )


def _stream_product_advice(state: dict, total_started: float, route: str, db, get_default_retrieval_agent: Callable):
    """Run cache, retrieval, advisor, verification, regeneration, and final event."""
    cached = _lookup_semantic_cache(state)
    if cached:
        yield from _stream_cached_response(state, cached, total_started, route)
        return

    state, docs = _run_retrieval(state, db, get_default_retrieval_agent)
    if not docs:
        yield from _stream_no_context_response(state, total_started, route)
        return

    yield {"sources": state.get("sources", [])}
    full = yield from _stream_answer_tokens(
        stream_advisor_tokens(state),
        first_token_step="advisor_first_token",
        generation_step="advisor_generation",
    )

    num_docs = len(state.get("retrieved_docs", []))
    verdict, low_confidence = _evaluate_answer_phase(full, state, num_docs)
    full, verdict, low_confidence = yield from _stream_regenerations(
        state,
        full,
        verdict,
        low_confidence,
        num_docs,
    )

    yield from _stream_low_confidence_warning(verdict, low_confidence)
    _save_semantic_cache_if_eligible(state, full, low_confidence)
    yield {
        "final": {
            **state,
            "answer": full,
            "low_confidence": low_confidence,
            "groundedness_inline": verdict["groundedness"],
        }
    }
    _log_timing(
        "total",
        total_started,
        route=route,
        docs=num_docs,
        chars=len(full),
        low_confidence=low_confidence,
    )


def stream_chat_events(
    query: str,
    history: str,
    db,
    temperature: float | None,
    top_k: int | None,
    get_default_retrieval_agent: Callable,
):
    """Yield the full streaming event sequence for one chat turn."""
    total_started = time.perf_counter()
    state = _build_initial_state(query, history, temperature, top_k)
    state, route = _route_with_supervisor(state, query)

    if route in ("invalid",) or (route == "smalltalk" and not state.get("query")):
        yield from _stream_terminal_response(
            state,
            total_started,
            route,
            state.get("answer", ""),
        )
        return

    if route == "smalltalk":
        yield from _stream_smalltalk_response(state, total_started, route)
        return

    yield from _stream_product_advice(
        state,
        total_started,
        route,
        db,
        get_default_retrieval_agent,
    )
