import os
from dataclasses import dataclass
from pathlib import Path
import yaml
from django.conf import settings

BASE_DIR = settings.BASE_DIR


with open(BASE_DIR / ".config" / "config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)


@dataclass(frozen=True) # not allow to modify after initialization
class Settings:
    base_dir: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "data"
    storage_dir: Path = BASE_DIR / "storage"
    prompt_path: Path = BASE_DIR / "prompts"
    
    # loader
    loader_type: str = config['loader']['type']
    
    # embedding
    embedding_provider: str = config['embedding']['embedding_provider']
    embedding_model: str = config['embedding']['embedding_model']
    embedding_dimension: int = config['embedding']['dimension']
    embedding_device: str = os.getenv(
        "EMBEDDING_DEVICE",
        config["embedding"].get("device", "auto"),
    ).lower()
    embedding_batch_size: int = int(
        os.getenv("EMBEDDING_BATCH_SIZE", config["embedding"].get("batch_size", 2))
    )
    embedding_max_seq_length: int = int(
        os.getenv("EMBEDDING_MAX_SEQ_LENGTH", config["embedding"].get("max_seq_length", 512))
    )
    qdrant_ingest_batch_size: int = int(
        os.getenv("QDRANT_INGEST_BATCH_SIZE", config["embedding"].get("ingest_batch_size", 8))
    )
    
    # Splitter
    splitter_method: str = config["splitter"]["method"]

    # LLM MODEL
    llm_provider: str = os.getenv("LLM_PROVIDER", config["llm"]["provider"]).lower()
    llm_model: str = os.getenv("LLM_MODEL", config["llm"]["model"])
    supervisor_llm_model: str = os.getenv(
        "SUPERVISOR_LLM_MODEL",
        os.getenv("LLM_MODEL", config["llm"].get("supervisor_model", config["llm"]["model"])),
    )
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_api_key: str | None = os.getenv('OPENAI_API_KEY')
    
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "5"))
    rag_temperature: float = float(os.getenv("RAG_TEMPERATURE", "0.1"))

    # Semantic answer cache
    semantic_cache_enabled: bool = os.getenv(
        "SEMANTIC_CACHE_ENABLED", str(config["semantic_cache"]["enabled"])
    ).lower() in {
        "1",
        "true",
        "yes",
    }
    semantic_cache_collection: str = os.getenv(
        "SEMANTIC_CACHE_COLLECTION", config["semantic_cache"]["collection"]
    )
    semantic_cache_threshold: float = float(
        os.getenv("SEMANTIC_CACHE_THRESHOLD", config["semantic_cache"]["threshold"])
    )
    semantic_cache_ttl_hours: int = int(
        os.getenv("SEMANTIC_CACHE_TTL_HOURS", config["semantic_cache"]["ttl_hours"])
    )
    semantic_cache_limit: int = int(
        os.getenv("SEMANTIC_CACHE_LIMIT", config["semantic_cache"].get("limit", 5))
    )

    # Vector database (Qdrant) settings
    vector_backend: str = config.get("vector", {}).get("backend", "qdrant")
    qdrant_url: str | None = os.getenv("QDRANT_URL")  # connection info -> giữ ở .env
    qdrant_api_key: str | None = os.getenv("QDRANT_API_KEY")  # secret -> giữ ở .env
    qdrant_collection: str = os.getenv(
        "QDRANT_COLLECTION", config["vector"]["collection"]
    )
    qdrant_timeout: int = int(os.getenv("QDRANT_TIMEOUT", "60"))
    qdrant_prefer_grpc: bool = os.getenv("QDRANT_PREFER_GRPC", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    
    # chunking settings from config.yaml
    chunk_size: int = config["chunking"]["chunk_size"]
    chunk_overlap: int = config["chunking"]["chunk_overlap"]
    
    # retriever
    score_threshold: float = config["retriever"]["score_threshold"]
    
    # search
    hybrid_enabled: bool = config.get("retriever", {}).get("hybrid_enabled", False)
    sparse_model: str = config.get("retriever", {}).get("sparse_model", "Qdrant/bm25")
    self_query_enabled: bool = config.get("retriever", {}).get("self_query_enabled", True)

    # reranker settings from config.yaml
    reranker_enabled: bool = config.get("reranker", {}).get("enabled", False)
    reranker_model: str = config.get("reranker", {}).get(
        "model", "Alibaba-NLP/gte-multilingual-reranker-base"
    )
    reranker_top_n: int = config.get("reranker", {}).get("top_n", 5)
    reranker_candidate_multiplier: int = config.get("reranker", {}).get(
        "candidate_multiplier", 3
    )
    hallucination_threshold: float = config.get("reranker", {}).get(
        "hallucination_threshold", 0.5
    )
    min_rerank_score: float = config.get("reranker", {}).get("min_rerank_score", 0.0)
    regenerate_enabled: bool = config.get("reranker", {}).get("regenerate_enabled", True)
    regenerate_threshold: float = config.get("reranker", {}).get("regenerate_threshold", 0.4)
    max_regenerations: int = config.get("reranker", {}).get("max_regenerations", 1)

    # chat history settings from config.yaml
    num_chats_retained: int = config["chat_history"]["num_chats_retained"]
    max_length: int = config["chat_history"]["max_length"]
    beam_size: int = config["chat_history"]["beam_size"]


settings = Settings()
