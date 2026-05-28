"""Verify that citations in an LLM answer are valid against the cited context.

The advisor prompt requires every claim that mentions product data to be tagged
with ``[N]`` where N is the citation index assigned by the retrieval agent.
This module checks the answer for:

- Are there any citations at all? (substantive answers should have some.)
- Do all cited indices exist in the retrieved docs?
- What fraction of cited indices fall outside the valid range?
"""

from __future__ import annotations

import re


_CITATION_RE = re.compile(r"\[(\d+)\]")
_SUBSTANTIVE_MIN_WORDS = 15


def parse_citations(text: str) -> list[int]:
    """Return all numeric citation indices found in ``text`` (deduped, ordered)."""
    seen: list[int] = []
    for match in _CITATION_RE.finditer(text or ""):
        try:
            num = int(match.group(1))
        except ValueError:
            continue
        if num not in seen:
            seen.append(num)
    return seen


def verify_citations(answer: str, num_docs: int) -> dict:
    """Check that citations in ``answer`` point to valid doc indices.

    Returns a report dict with::

        {
          "citations": [list of cited ints],
          "invalid": [list of ints outside 1..num_docs],
          "missing": True if substantive answer has zero citations,
          "ok": True iff invalid==[] and not missing,
        }
    """
    citations = parse_citations(answer)
    invalid = [c for c in citations if c < 1 or c > num_docs]
    word_count = len((answer or "").split())
    missing = word_count >= _SUBSTANTIVE_MIN_WORDS and not citations
    return {
        "citations": citations,
        "invalid": invalid,
        "missing": missing,
        "ok": not invalid and not missing,
    }
