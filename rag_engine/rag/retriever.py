import logging

from rag_engine.core.config import settings
from rag_engine.rag.tools import build_qdrant_filter

logger = logging.getLogger(__name__)


def _is_qdrant_timeout(exc: Exception) -> bool:
    text = str(exc).lower()
    return "deadline_exceeded" in text or "deadline exceeded" in text


def retrieve(
    db,
    query,
    k: int = 10,
    score_threshold: float | None = None,
    filters: dict | None = None,
):
    """Find the k most similar documents to the query using similarity search.

    ``score_threshold`` is opt-in. When the reranker is enabled the threshold is
    normally bypassed so the cross-encoder gets a full candidate set to score.

    ``filters`` is an LLM-extracted constraint dict converted to a Qdrant Filter.
    If Qdrant rejects the filter, the search is retried without it so chat still
    works. If Qdrant times out, return no documents so the pipeline can answer
    through its no-context guardrail instead of failing the whole request.
    """
    threshold = score_threshold if score_threshold is not None else settings.score_threshold
    qdrant_filter = build_qdrant_filter(filters)

    kwargs = {"k": k}
    if threshold and threshold > 0:
        kwargs["score_threshold"] = threshold
    if qdrant_filter is not None:
        kwargs["filter"] = qdrant_filter

    try:
        return db.similarity_search(query, **kwargs)
    except Exception as exc:
        if _is_qdrant_timeout(exc):
            logger.warning("Qdrant search timed out; returning no retrieved documents.")
            return []
        if qdrant_filter is None:
            raise

        logger.warning("Qdrant filter rejected (%s) - retrying without filter.", exc)
        kwargs.pop("filter", None)
        try:
            return db.similarity_search(query, **kwargs)
        except Exception as retry_exc:
            if _is_qdrant_timeout(retry_exc):
                logger.warning("Qdrant unfiltered retry timed out; returning no retrieved documents.")
                return []
            raise
