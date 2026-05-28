from rag_engine.core.config import settings
from rag_engine.rag.tools import build_qdrant_filter


def retrieve(
    db,
    query,
    k: int = 10,
    score_threshold: float | None = None,
    filters: dict | None = None,
):
    """Find the k most similar documents to the query using similarity search.

    ``score_threshold`` is opt-in. When the reranker is enabled the threshold is
    normally bypassed so the cross-encoder gets a full candidate set to score —
    pass an explicit value if you need pre-filtering.

    ``filters`` is an LLM-extracted constraint dict (brand, price_max, ram_min…)
    converted to a Qdrant Filter and applied server-side before similarity
    scoring — narrows the candidate pool to docs that match the user's stated
    requirements.
    """
    threshold = score_threshold if score_threshold is not None else settings.score_threshold
    qdrant_filter = build_qdrant_filter(filters)

    kwargs = {"k": k}
    if threshold and threshold > 0:
        kwargs["score_threshold"] = threshold
    if qdrant_filter is not None:
        kwargs["filter"] = qdrant_filter

    return db.similarity_search(query, **kwargs)
