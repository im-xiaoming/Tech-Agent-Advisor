"""Supervisor agent: classify intent and decide route for the graph."""

from rag_engine.agents.state import AgentState
from rag_engine.core.config import settings
from rag_engine.core.llm import classify_and_rewrite


def supervisor_agent(state: AgentState) -> AgentState:
    """Normalize the query and classify intent: invalid / smalltalk / product_advice."""
    query = state.get("query", "").strip()
    if not query:
        return {
            **state,
            "route": "invalid",
            "error": "Query is empty.",
            "answer": "Vui lòng nhập câu hỏi về sản phẩm cần tư vấn.",
        }

    decision = classify_and_rewrite(query, history=state.get("history", ""))
    intent = decision["intent"]
    filters = decision.get("filters", {}) if settings.self_query_enabled else {}

    if intent == "invalid":
        return {
            **state,
            "query": query,
            "original_query": query,
            "filters": {},
            "route": "invalid",
            "error": "Unable to classify intent.",
            "answer": "Xin lỗi, tôi không hiểu câu hỏi của bạn. Vui lòng hỏi về sản phẩm hoặc trò chuyện nhé.",
        }

    if intent == "smalltalk":
        return {
            **state,
            "query": query,
            "original_query": query,
            "filters": {},
            "route": "smalltalk",
        }

    return {
        **state,
        "query": decision["rewritten"],
        "original_query": query,
        "filters": filters,
        "route": "product_advice",
    }
