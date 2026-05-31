"""API cấp cao để hỏi chatbot RAG từ code Django hoặc CLI."""

from functools import lru_cache

from rag_engine.agents.graph import build_chat_graph
from rag_engine.agents.retrieval.agent import make_retrieval_agent
from rag_engine.core.config import settings
from rag_engine.rag.pipeline_stream import stream_chat_events
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


def ask(query: str, history: str, db=None, temperature: float | None = None, top_k: int | None = None) -> dict:
    """Run the compiled graph synchronously and return a normalized result dict."""
    graph = (
        build_chat_graph(db, top_k=top_k or settings.rag_top_k)
        if db is not None
        else get_default_graph()
    )

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
    yield from stream_chat_events(
        query=query,
        history=history,
        db=db,
        temperature=temperature,
        top_k=top_k,
        get_default_retrieval_agent=_get_retrieval_agent,
    )
