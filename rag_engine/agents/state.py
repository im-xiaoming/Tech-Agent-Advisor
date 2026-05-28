"""Data schema for the state passed between agents in the LangGraph."""

from typing import Literal, NotRequired, TypedDict
from langchain_core.documents import Document


class AgentState(TypedDict):
    query: str
    original_query: NotRequired[str]
    history: NotRequired[str]
    filters: NotRequired[dict]
    route: NotRequired[Literal["product_advice", "smalltalk", "invalid"]]
    retrieved_docs: NotRequired[list[Document]]
    context: NotRequired[str]
    answer: NotRequired[str]
    error: NotRequired[str]
    sources: NotRequired[list[str]]
    top_k: NotRequired[int]
    temperature: NotRequired[float]
