from functools import lru_cache
from rag_engine.core.config import settings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaEmbeddings
import torch


@lru_cache(maxsize=1)
def get_embeddings():
    """
    Return a cached Embeddings instance based on LLM Provider for encoding documents and queries.
    
    Returns:
        Embeddings: An instance of Embeddings initialized with the configured model.
    """
    
    if settings.embedding_provider == 'ollama':
        print("Use Ollama Embedding...")
        return OllamaEmbeddings(
            model=settings.embedding_model,
            dimensions=settings.embedding_dimension,
        )
    else:
        print("Use HuggingFaceEmbeddings...")
        return HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "gpu" if torch.cuda.is_available() else "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
