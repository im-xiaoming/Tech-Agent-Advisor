"""Supervisor agent: classify intent and decide route for the graph."""

from rag_engine.agents.state import AgentState
from transformers import pipeline
from functools import lru_cache
import os
import torch


@lru_cache(maxsize=1)
def get_classifier():
    return pipeline(
        "zero-shot-classification",
        model=os.getenv("CLASSIFICATION_MODEL", "joeddav/xlm-roberta-large-xnli"),
        device='cuda' if torch.cuda.is_available() else 'cpu'
    )


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
        
    classifier = get_classifier()
    result = classifier(
        query,
        candidate_labels=["smalltalk", "product_advice", "invalid"],
        hypothesis_template="Câu này thuộc nhóm {}.",
    )

    if result["labels"][0] == "smalltalk":
        return {**state, "query": query, "route": "smalltalk"}
    elif result["labels"][0] == "product_advice":
        return {**state, "query": query, "route": "product_advice"}
    else:
        return {
            **state,
            "query": query,
            "route": "invalid",
            "error": "Unable to classify intent.",
            "answer": "Xin lỗi, tôi không hiểu câu hỏi của bạn. Vui lòng hỏi về sản phẩm hoặc trò chuyện nhé.",
        }
