from langchain_core.vectorstores import VectorStore

from rag_engine.agents.state import AgentState
from rag_engine.core.config import settings
from rag_engine.rag.retriever import retrieve
from rag_engine.rag.tools import rerank_documents


_PRODUCT_TYPE_TERMS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("tai nghe", "headphone", "headphones", "earphone", "earphones", "earbud", "earbuds", "airpods", "buds"),
        ("tai nghe", "headphone", "headset", "earphone", "earbud", "airpods", "buds", "inzone", "wh-", "wf-"),
    ),
)


def _text(doc) -> str:
    metadata = getattr(doc, "metadata", {}) or {}
    return " ".join(
        str(value or "")
        for value in (
            metadata.get("title"),
            metadata.get("source"),
            getattr(doc, "page_content", ""),
        )
    ).lower()


def _matching_product_terms(query: str) -> tuple[str, ...]:
    normalized = query.lower()
    for query_terms, doc_terms in _PRODUCT_TYPE_TERMS:
        if any(term in normalized for term in query_terms):
            return doc_terms
    return ()


def _filter_product_type(query: str, docs: list) -> list:
    doc_terms = _matching_product_terms(query)
    if not doc_terms:
        return docs
    return [doc for doc in docs if any(term in _text(doc) for term in doc_terms)]


def _fetch_and_rerank(db, query: str, top_k: int, filters: dict | None):
    if settings.reranker_enabled:
        fetch_k = max(top_k, top_k * settings.reranker_candidate_multiplier)
        candidates = retrieve(db, query, k=fetch_k, filters=filters)
        candidates = _filter_product_type(query, candidates)
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
    return _filter_product_type(query, retrieve(db, query, k=top_k, filters=filters))


def make_retrieval_agent(db: VectorStore, default_top_k: int):
    """Create retrieval agent that attaches a vector store with top_k value by default."""

    def retrieval_agent(state: AgentState) -> AgentState:
        """Find relevant documents, assemble context, and collect sources list."""
        top_k = int(state.get("top_k") or default_top_k)
        query = state["query"]
        filters = state.get("filters") or {}

        docs = _fetch_and_rerank(db, query, top_k, filters)

        # Fallback A: relax filters if they killed all results.
        if not docs and filters:
            docs = _fetch_and_rerank(db, query, top_k, None)

        # Fallback B: retry with the original (un-rewritten) query.
        original_query = state.get("original_query")
        if not docs and original_query and original_query != query:
            docs = _fetch_and_rerank(db, original_query, top_k, None)

        # Number each doc so the advisor can cite them as [1], [2]…
        numbered_blocks = []
        for idx, doc in enumerate(docs, start=1):
            doc.metadata["citation_index"] = idx
            numbered_blocks.append(f"[{idx}]\n{doc.page_content}")
        context = "\n\n".join(numbered_blocks)
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
