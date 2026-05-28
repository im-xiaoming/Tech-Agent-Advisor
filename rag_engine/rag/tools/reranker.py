"""Cross-encoder reranking for retrieved documents.

Uses ``Alibaba-NLP/gte-multilingual-reranker-base`` by default — a multilingual
cross-encoder that scores (query, document) pairs and lets us re-order the
candidate set produced by vector similarity search so the most relevant
passages end up in the LLM context window.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable

from langchain_core.documents import Document

from rag_engine.core.config import settings


class Reranker:
    """Lazy wrapper around a HuggingFace sequence-classification reranker."""

    def __init__(self, model_name: str | None = None, max_length: int = 512):
        self.model_name = model_name or settings.reranker_model
        self.max_length = max_length
        self._tokenizer = None
        self._model = None
        self._torch = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name,
            trust_remote_code=True,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        )
        self._model.eval()
        if torch.cuda.is_available():
            self._model = self._model.cuda()

    def score(self, query: str, texts: Iterable[str]) -> list[float]:
        texts = list(texts)
        if not texts:
            return []
        self._ensure_loaded()
        pairs = [[query, text] for text in texts]
        with self._torch.no_grad():
            inputs = self._tokenizer(
                pairs,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=self.max_length,
            )
            if self._torch.cuda.is_available():
                inputs = {key: value.cuda() for key, value in inputs.items()}
            logits = self._model(**inputs, return_dict=True).logits.view(-1).float()
            # Squash to [0, 1] so downstream code (UI, thresholds) reads as a
            # probability-like score instead of raw, unbounded logits.
            scores = self._torch.sigmoid(logits)
            return scores.cpu().tolist()

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_n: int | None = None,
    ) -> list[Document]:
        if not documents:
            return []
        scores = self.score(query, (doc.page_content for doc in documents))
        ranked = sorted(zip(documents, scores), key=lambda pair: pair[1], reverse=True)
        limit = top_n or len(ranked)
        results: list[Document] = []
        for doc, score in ranked[:limit]:
            doc.metadata = {**doc.metadata, "rerank_score": float(score)}
            results.append(doc)
        return results


@lru_cache(maxsize=1)
def _default_reranker() -> Reranker:
    return Reranker()


def rerank_documents(
    query: str,
    documents: list[Document],
    top_n: int | None = None,
) -> list[Document]:
    """Re-rank ``documents`` against ``query`` using the configured model."""
    return _default_reranker().rerank(query, documents, top_n=top_n)
