from functools import lru_cache

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from rag_engine.core.config import settings
from rag_engine.core.embedding import get_embeddings


DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"

# Payload indexes required for self-query metadata filtering. Qdrant rejects
# Filter conditions on fields that don't have an index; we ensure them on both
# new collections and pre-existing ones at load time.
_PAYLOAD_INDEXES: tuple[tuple[str, "qmodels.PayloadSchemaType"], ...] = (
    ("metadata.price", qmodels.PayloadSchemaType.FLOAT),
    ("metadata.ram_gb", qmodels.PayloadSchemaType.FLOAT),
    ("metadata.storage_gb", qmodels.PayloadSchemaType.FLOAT),
    ("metadata.battery_mah", qmodels.PayloadSchemaType.FLOAT),
    ("metadata.brand", qmodels.PayloadSchemaType.TEXT),
)


def _ensure_payload_indexes(client: QdrantClient, name: str) -> None:
    """Create payload indexes for filter fields. Idempotent."""
    for field, schema in _PAYLOAD_INDEXES:
        try:
            client.create_payload_index(
                collection_name=name,
                field_name=field,
                field_schema=schema,
            )
        except Exception:
            # Already exists, or the field has heterogeneous types in old data
            # — log and continue. Filter will fall back to no-filter at search.
            pass


def _get_client() -> QdrantClient:
    """Initialize a Qdrant client pointing to Qdrant Cloud."""
    if not settings.qdrant_url:
        raise ValueError("QDRANT_URL is required when using Qdrant backend.")
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        prefer_grpc=True,
    )


def _embedding_dim() -> int:
    """Detect embedding dimension dynamically from the active model."""
    return len(get_embeddings().embed_query("dim probe"))


@lru_cache(maxsize=1)
def _get_sparse_embeddings():
    """Lazy-load FastEmbed sparse model for hybrid search."""
    from langchain_qdrant import FastEmbedSparse

    return FastEmbedSparse(model_name=settings.sparse_model)


def _collection_names(client: QdrantClient) -> set[str]:
    """Return all collection names currently available in Qdrant."""
    return {c.name for c in client.get_collections().collections}


def _create_collection(client: QdrantClient, name: str, dim: int) -> None:
    """Create a Qdrant collection sized for the active retrieval mode."""
    if settings.hybrid_enabled:
        client.create_collection(
            collection_name=name,
            vectors_config={
                DENSE_VECTOR_NAME: qmodels.VectorParams(
                    size=dim, distance=qmodels.Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: qmodels.SparseVectorParams(),
            },
        )
    else:
        client.create_collection(
            collection_name=name,
            vectors_config=qmodels.VectorParams(
                size=dim, distance=qmodels.Distance.COSINE,
            ),
        )


def _recreate_collection(client: QdrantClient, name: str, dim: int) -> None:
    """Delete an existing collection before creating a fresh one for rebuilds."""
    if name in _collection_names(client):
        client.delete_collection(collection_name=name)
    _create_collection(client, name, dim)


def _build_vector_store(client: QdrantClient, name: str) -> QdrantVectorStore:
    if settings.hybrid_enabled:
        from langchain_qdrant import RetrievalMode

        return QdrantVectorStore(
            client=client,
            collection_name=name,
            embedding=get_embeddings(),
            sparse_embedding=_get_sparse_embeddings(),
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name=DENSE_VECTOR_NAME,
            sparse_vector_name=SPARSE_VECTOR_NAME,
        )
    return QdrantVectorStore(
        client=client,
        collection_name=name,
        embedding=get_embeddings(),
    )


def create_qdrant_db(chunks, collection_name: str | None = None):
    """Rebuild a Qdrant collection from chunks and return the vector store."""
    if not chunks:
        raise ValueError("Cannot create Qdrant collection from empty chunks.")

    name = collection_name or settings.qdrant_collection
    client = _get_client()
    _recreate_collection(client, name, _embedding_dim())
    _ensure_payload_indexes(client, name)

    store = _build_vector_store(client, name)

    batch_size = 32
    mode = "hybrid (dense+sparse)" if settings.hybrid_enabled else "dense"
    print(f"Ingesting {len(chunks)} chunks into Qdrant '{name}' [{mode}]...")
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        print(f"  batch {i} -> {i + len(batch)}")
        store.add_documents(batch)

    print(f"Done. Collection '{name}' rebuilt on Qdrant Cloud.")
    return store


def load_qdrant_db(collection_name: str | None = None):
    """Load the Qdrant vector store for an existing collection."""
    name = collection_name or settings.qdrant_collection
    client = _get_client()

    if name not in _collection_names(client):
        raise ValueError(f"Qdrant collection '{name}' not found.")

    _ensure_payload_indexes(client, name)
    return _build_vector_store(client, name)


def count_qdrant_vectors(db) -> int:
    """Count the number of points (vectors) currently stored in the collection."""
    info = db.client.get_collection(db.collection_name)
    return info.points_count or 0
