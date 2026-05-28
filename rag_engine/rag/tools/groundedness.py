"""Heuristic groundedness check used to flag potential hallucinations.

Reuses the cross-encoder reranker to score the generated answer against each
context chunk. The max score is taken as the groundedness signal — high means
at least one supporting passage exists; low means the answer is likely not
supported by the retrieved context.
"""

from __future__ import annotations

from langchain_core.documents import Document

from .reranker import _default_reranker


def _split_context(context: str) -> list[str]:
    chunks = [chunk.strip() for chunk in context.split("\n\n") if chunk.strip()]
    return chunks or ([context.strip()] if context.strip() else [])


def score_answer(answer: str, context: str) -> float | None:
    """Return the max cross-encoder score between ``answer`` and any context chunk."""
    if not answer or not answer.strip() or not context or not context.strip():
        return None
    chunks = _split_context(context)
    if not chunks:
        return None
    scores = _default_reranker().score(answer, chunks)
    return max(scores) if scores else None


def score_answer_against_docs(answer: str, docs: list[Document]) -> float | None:
    if not answer or not answer.strip() or not docs:
        return None
    texts = [doc.page_content for doc in docs if getattr(doc, "page_content", "")]
    if not texts:
        return None
    scores = _default_reranker().score(answer, texts)
    return max(scores) if scores else None
