from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from rag_engine.core.config import settings
from rag_engine.core.embedding import get_embeddings


def _get_client() -> QdrantClient:
    """Initialize a Qdrant client pointing to Qdrant Cloud."""
    if not settings.qdrant_url:
        raise ValueError("QDRANT_URL is required when using Qdrant backend.")
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        prefer_grpc=False,
    )


def _embedding_dim() -> int:
    """
    Get the embedding dimension by embedding a test string.
    
    Returns:
        int: The dimension of the embedding vectors. 1024 is default for BAAI/bge-m3, but this method allows dynamic detection in case the model changes.
    """
    return len(get_embeddings().embed_query("dim probe"))


def _collection_names(client: QdrantClient) -> set[str]:
    """Return all collection names currently available in Qdrant."""
    return {c.name for c in client.get_collections().collections}


def _create_collection(client: QdrantClient, name: str, dim: int) -> None:
    """Create a Qdrant collection with the expected vector configuration."""
    client.create_collection(
        collection_name=name,
        vectors_config=qmodels.VectorParams(
            size=dim,
            distance=qmodels.Distance.COSINE,
        ),
    )


def _recreate_collection(client: QdrantClient, name: str, dim: int) -> None:
    """Delete an existing collection before creating a fresh one for rebuilds."""
    if name in _collection_names(client):
        client.delete_collection(collection_name=name)
    _create_collection(client, name, dim)


def create_qdrant_db(chunks, collection_name: str | None = None):
    """
    Rebuild a Qdrant collection from chunks and return the vector store.
    
    Args:
        chunks (list): A list of document chunks to be indexed.
        collection_name (str, optional): The name of the Qdrant collection to rebuild. Defaults to None, which will use the collection name specified in settings.
        
    Returns:
        QdrantVectorStore: The initialized vector store connected to the rebuilt collection.
    """
    if not chunks:
        raise ValueError("Cannot create Qdrant collection from empty chunks.")

    name = collection_name or settings.qdrant_collection
    client = _get_client()
    _recreate_collection(client, name, _embedding_dim())

    store = QdrantVectorStore(
        client=client,
        collection_name=name,
        embedding=get_embeddings(),
    )

    batch_size = 32
    print(f"Ingesting {len(chunks)} chunks into Qdrant collection '{name}'...")
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

    return QdrantVectorStore(
        client=client,
        collection_name=name,
        embedding=get_embeddings(),
    )


def count_qdrant_vectors(db) -> int:
    """Count the number of points (vectors) currently stored in the collection."""
    info = db.client.get_collection(db.collection_name)
    return info.points_count or 0
