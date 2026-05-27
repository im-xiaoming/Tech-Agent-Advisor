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
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

    # LLM MODEL
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama").lower()
    llm_model: str = os.getenv("LLM_MODEL", 'jaahas/qwen3.5-uncensored')
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "10"))
    rag_temperature: float = float(os.getenv("RAG_TEMPERATURE", "0.1"))

    # Vector database (Qdrant) settings
    qdrant_url: str | None = os.getenv("QDRANT_URL")
    qdrant_api_key: str | None = os.getenv("QDRANT_API_KEY")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "tech_products")
    
    # chunking settings from config.yaml
    chunk_size: int = config["chunking"]["chunk_size"]
    chunk_overlap: int = config["chunking"]["chunk_overlap"]
    score_threshold: float = config["retriever"]["score_threshold"]
    
    # chat history settings from config.yaml
    num_chats_retained: int = config["chat_history"]["num_chats_retained"]
    max_length: int = config["chat_history"]["max_length"]
    beam_size: int = config["chat_history"]["beam_size"]


settings = Settings()
