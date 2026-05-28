from rag_engine.core.config import settings


def retrieve(db, query, k=10, score_threshold: float | None = None):
    """Find the k most similar documents to the query using similarity search.

    ``score_threshold`` is opt-in. When the reranker is enabled the threshold is
    normally bypassed so the cross-encoder gets a full candidate set to score —
    pass an explicit value if you need pre-filtering.
    """
    threshold = score_threshold if score_threshold is not None else settings.score_threshold
    if threshold and threshold > 0:
        return db.similarity_search(query, k=k, score_threshold=threshold)
    return db.similarity_search(query, k=k)
