"""API cấp cao để hỏi chatbot RAG từ code Django hoặc CLI."""

from functools import lru_cache

from rag_engine.agents.graph import build_chat_graph
from rag_engine.core.config import settings
from rag_engine.rag.vector_store import load_vector_db


@lru_cache(maxsize=1)
def get_default_db():
    """Load the configured Qdrant collection and cache it for later queries."""
    return load_vector_db()


@lru_cache(maxsize=1)
def get_default_graph():
    """Build and cache the default chat graph."""
    vector_db = get_default_db()
    return build_chat_graph(vector_db, top_k=settings.rag_top_k)


def ask(query: str, db=None, temperature: float | None = None, top_k: int | None = None) -> dict:
    vector_db = db or get_default_db()
    graph = get_default_graph()
    
    result = graph.invoke(
        {
            "query": query,
            "temperature": temperature if temperature is not None else settings.rag_temperature,
            "top_k": top_k or settings.rag_top_k,
        }
    )
    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "error": result.get("error"),
    }


def ask_rag(db, query, creative_level=0.1):
    return ask(query, db=db, temperature=creative_level)["answer"]
