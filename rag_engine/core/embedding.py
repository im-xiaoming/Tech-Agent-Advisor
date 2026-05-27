from functools import lru_cache
from rag_engine.core.config import settings


@lru_cache(maxsize=1)
def get_embeddings():
    """
    Return a cached HuggingFaceEmbeddings instance for encoding documents and queries.
    
    Returns:
        HuggingFaceEmbeddings: An instance of HuggingFaceEmbeddings initialized with the configured model.
    """
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
