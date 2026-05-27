from rag_engine.rag.vector_store_qdrant import (
    count_qdrant_vectors,
    create_qdrant_db,
    load_qdrant_db,
)


def create_vector_db(chunks):
    """Create or update the configured Qdrant collection from document chunks."""
    return create_qdrant_db(chunks)


def load_vector_db():
    """Load the configured Qdrant collection as a vector store."""
    return load_qdrant_db()


def count_vectors(db) -> int:
    """Count points currently stored in the configured Qdrant collection."""
    return count_qdrant_vectors(db)
