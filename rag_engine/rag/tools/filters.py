"""Build Qdrant filters from a structured dict of constraints.

The supervisor/LLM extracts intent-level filters from the natural language
query (e.g. "iPhone dưới 20 triệu RAM 8GB" → ``{"brand": "Apple",
"price_max": 20000000, "ram_min": 8}``). This module converts that dict
into a ``qdrant_client.http.models.Filter`` instance applied at search time.

Supported keys (all optional, all values must be plain Python scalars):
    brand        — str, matched case-insensitively against ``metadata.brand``
    price_min    — number, ``metadata.price >= price_min``
    price_max    — number, ``metadata.price <= price_max``
    ram_min      — number, ``metadata.ram_gb >= ram_min``
    storage_min  — number, ``metadata.storage_gb >= storage_min``
    battery_min  — number, ``metadata.battery_mah >= battery_min``
"""

from __future__ import annotations

from qdrant_client.http import models as qm


_NUMERIC_RULES: list[tuple[str, str, str]] = [
    ("price_min", "metadata.price", "gte"),
    ("price_max", "metadata.price", "lte"),
    ("ram_min", "metadata.ram_gb", "gte"),
    ("storage_min", "metadata.storage_gb", "gte"),
    ("battery_min", "metadata.battery_mah", "gte"),
]


def _to_number(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_qdrant_filter(filters: dict | None) -> qm.Filter | None:
    """Convert an LLM-extracted filter dict into a Qdrant Filter, or None."""
    if not filters or not isinstance(filters, dict):
        return None

    must: list[qm.FieldCondition] = []

    brand = filters.get("brand")
    if isinstance(brand, str) and brand.strip():
        # MatchText does substring match; tolerant of "Apple" vs "apple" vs "iPhone (Apple)".
        must.append(
            qm.FieldCondition(
                key="metadata.brand",
                match=qm.MatchText(text=brand.strip()),
            )
        )

    for source_key, field, op in _NUMERIC_RULES:
        value = _to_number(filters.get(source_key))
        if value is None:
            continue
        rng = qm.Range(**{op: value})
        must.append(qm.FieldCondition(key=field, range=rng))

    return qm.Filter(must=must) if must else None
