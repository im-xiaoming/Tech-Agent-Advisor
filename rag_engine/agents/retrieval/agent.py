from langchain_core.vectorstores import VectorStore

from rag_engine.agents.state import AgentState
from rag_engine.core.config import settings
from rag_engine.rag.retriever import retrieve
from rag_engine.rag.tools import rerank_documents


def _fetch_and_rerank(db, query: str, top_k: int):
    if settings.reranker_enabled:
        fetch_k = max(top_k, top_k * settings.reranker_candidate_multiplier)
        candidates = retrieve(db, query, k=fetch_k)
        if not candidates:
            return []
        ranked = rerank_documents(query, candidates, top_n=top_k)
        threshold = settings.min_rerank_score
        if threshold and threshold > 0:
            ranked = [
                doc for doc in ranked
                if (doc.metadata.get("rerank_score") or 0) >= threshold
            ]
        return ranked
    return retrieve(db, query, k=top_k)


def make_retrieval_agent(db: VectorStore, default_top_k: int):
    """Create retrieval agent that attaches a vector store with top_k value by default."""

    def retrieval_agent(state: AgentState) -> AgentState:
        """Find relevant documents, assemble context, and collect sources list."""
        top_k = int(state.get("top_k") or default_top_k)
        query = state["query"]

        docs = _fetch_and_rerank(db, query, top_k)

        # Fallback: if the rewritten query found nothing, retry with the original.
        original_query = state.get("original_query")
        if not docs and original_query and original_query != query:
            docs = _fetch_and_rerank(db, original_query, top_k)

        context = "\n\n".join(doc.page_content for doc in docs)
        sources = sorted(
            {
                str(doc.metadata.get("source"))
                for doc in docs
                if doc.metadata.get("source")
            }
        )

        return {
            **state,
            "retrieved_docs": docs,
            "context": context,
            "sources": sources,
        }

    return retrieval_agent
