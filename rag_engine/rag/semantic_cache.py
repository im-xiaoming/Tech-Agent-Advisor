"""Semantic answer cache backed by a separate Qdrant collection."""

from __future__ import annotations

import json
import logging
import threading
from datetime import timedelta
from uuid import uuid4

from django.db import close_old_connections
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from manager.models import SemanticCacheEntry
from rag_engine.core.config import settings


logger = logging.getLogger(__name__)


def _normalize_question(question: str) -> str:
    """Collapse whitespace so semantically identical questions embed consistently."""
    return " ".join(str(question or "").split())


def _normalize_filters(filters: dict | None) -> dict:
    """Convert filters into a stable JSON-compatible dict for exact comparison."""
    if not isinstance(filters, dict):
        return {}
    try:
        return json.loads(json.dumps(filters, ensure_ascii=False, sort_keys=True))
    except (TypeError, ValueError):
        return {}


def _get_client():
    """Create a Qdrant client for the cache collection."""
    if not settings.qdrant_url:
        raise ValueError("QDRANT_URL is required for semantic cache.")

    from qdrant_client import QdrantClient

    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        prefer_grpc=settings.qdrant_prefer_grpc,
        timeout=settings.qdrant_timeout,
    )


def _ensure_collection(client, vector_size: int) -> None:
    """Create the cache collection if it does not already exist."""
    collection_name = settings.semantic_cache_collection
    try:
        if client.collection_exists(collection_name):
            return
    except Exception:
        try:
            client.get_collection(collection_name)
            return
        except Exception:
            pass

    from qdrant_client.http import models as qmodels

    try:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=qmodels.VectorParams(
                size=vector_size,
                distance=qmodels.Distance.COSINE,
            ),
        )
    except Exception:
        # Another request may have created it between collection_exists and here.
        client.get_collection(collection_name)


def _embed_question(question: str) -> list[float]:
    """Embed one cache question with the configured embedding model."""
    from rag_engine.core.embedding import get_embeddings

    return get_embeddings().embed_query(question)


def _query_cache_points(client, vector: list[float]):
    """Search cache points using whichever Qdrant client API is available."""
    kwargs = {
        "collection_name": settings.semantic_cache_collection,
        "limit": settings.semantic_cache_limit,
        "score_threshold": settings.semantic_cache_threshold,
        "with_payload": True,
    }

    if hasattr(client, "query_points"):
        result = client.query_points(query=vector, **kwargs)
        return getattr(result, "points", result)

    return client.search(query_vector=vector, **kwargs)


def _payload_not_expired(payload: dict) -> bool:
    """Return whether a cache payload is still within its TTL."""
    expires_at = parse_datetime(str(payload.get("expires_at") or ""))
    if not expires_at:
        return True
    if timezone.is_naive(expires_at):
        expires_at = timezone.make_aware(expires_at)
    return expires_at > timezone.now()


def _record_cache_hit(entry_id, similarity: float) -> None:
    """Best-effort update of admin-visible hit metadata."""
    if not entry_id:
        return
    try:
        SemanticCacheEntry.objects.filter(pk=entry_id).update(
            hit_count=F("hit_count") + 1,
            last_hit_at=timezone.now(),
            similarity=similarity,
        )
    except Exception:
        logger.exception("Failed to record semantic cache hit.")


def get_cached_answer(question: str, filters: dict | None = None) -> dict | None:
    """Return a semantically similar cached answer, or None on miss/error."""
    if not settings.semantic_cache_enabled:
        return None

    normalized_question = _normalize_question(question)
    if not normalized_question:
        return None

    normalized_filters = _normalize_filters(filters)

    try:
        vector = _embed_question(normalized_question)
        client = _get_client()
        _ensure_collection(client, len(vector))
        points = _query_cache_points(client, vector)
    except Exception:
        logger.exception("Semantic cache lookup failed.")
        return None

    for point in points:
        payload = getattr(point, "payload", {}) or {}
        similarity = float(getattr(point, "score", 0.0) or 0.0)
        if payload.get("model") != settings.llm_model:
            continue
        if _normalize_filters(payload.get("filters")) != normalized_filters:
            continue
        if not _payload_not_expired(payload):
            continue

        entry_id = payload.get("entry_id")
        _record_cache_hit(entry_id, similarity)
        return {
            "question": payload.get("question", ""),
            "answer": payload.get("answer", ""),
            "sources": payload.get("sources", []) or [],
            "filters": payload.get("filters", {}) or {},
            "model": payload.get("model", ""),
            "similarity": similarity,
            "entry_id": entry_id,
        }

    return None


def save_answer_cache(
    *,
    question: str,
    answer: str,
    sources: list,
    filters: dict | None,
    model_name: str,
) -> None:
    """Persist an answer in Django admin and the semantic cache collection."""
    if not settings.semantic_cache_enabled:
        return

    normalized_question = _normalize_question(question)
    if not normalized_question or not answer:
        return

    normalized_filters = _normalize_filters(filters)
    now = timezone.now()
    expires_at = now + timedelta(hours=max(settings.semantic_cache_ttl_hours, 1))
    point_id = str(uuid4())

    entry = SemanticCacheEntry.objects.create(
        question=normalized_question,
        answer=answer,
        sources=sources or [],
        filters=normalized_filters,
        model_name=model_name,
        vector_point_id=point_id,
        expires_at=expires_at,
    )

    try:
        vector = _embed_question(normalized_question)
        client = _get_client()
        _ensure_collection(client, len(vector))

        from qdrant_client.http import models as qmodels

        client.upsert(
            collection_name=settings.semantic_cache_collection,
            points=[
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "entry_id": entry.pk,
                        "question": normalized_question,
                        "answer": answer,
                        "sources": sources or [],
                        "filters": normalized_filters,
                        "created_at": now.isoformat(),
                        "expires_at": expires_at.isoformat(),
                        "model": model_name,
                    },
                )
            ],
        )
    except Exception:
        logger.exception("Failed to persist semantic cache vector.")


def save_answer_cache_async(**kwargs) -> None:
    """Save semantic cache in a background thread so streaming is not blocked."""

    def _target():
        close_old_connections()
        try:
            save_answer_cache(**kwargs)
        finally:
            close_old_connections()

    threading.Thread(target=_target, daemon=True).start()
