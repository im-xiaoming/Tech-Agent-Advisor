from functools import lru_cache
from rag_engine.core.config import settings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings
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
    elif settings.embedding_provider == 'openai':
        
        print("Use OpenAI Embedding...")
        return OpenAIEmbeddings(
            model=settings.embedding_model,
            # With the `text-embedding-3` class
            # of models, you can specify the size
            # of the embeddings you want returned.
            dimensions=settings.embedding_dimension
        )
    else:
        print("Use HuggingFaceEmbeddings...")
        device = settings.embedding_device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": device},
            encode_kwargs={
                "normalize_embeddings": True,
                "batch_size": settings.embedding_batch_size,
            },
        )
        if settings.embedding_max_seq_length > 0:
            embeddings._client.max_seq_length = settings.embedding_max_seq_length
        return embeddings
