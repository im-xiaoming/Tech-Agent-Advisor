"""Pipeline ingestion to build the Qdrant vector collection from source data."""

from rag_engine.core.config import settings
from rag_engine.rag.chunking import split_docs
from rag_engine.rag.loader import load_data
from rag_engine.rag.vector_store import create_vector_db


def build_index(data_dir=None):
    """
    Load data, split it into chunks, and write it to Qdrant.
    
    Args:
        data_dir (str, optional): The directory containing the source data. Defaults to None, which will use the data_dir specified in settings.
    
    Returns:
        VectorDB: The initialized vector database with the indexed documents.
    """
    docs = load_data(data_dir or settings.data_dir)
    chunks = split_docs(docs)
    return create_vector_db(chunks)
