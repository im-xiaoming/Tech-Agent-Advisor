import json
import re
import unicodedata
from pathlib import Path
from typing import Iterator

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from rag_engine.core.config import settings


_MP_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*mp", re.IGNORECASE)
_APERTURE_RE = re.compile(r"f\s*/\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
_GB_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*gb", re.IGNORECASE)
_MAH_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*mah", re.IGNORECASE)


def _clean_text(value) -> str:
    text = str(value or "")
    try:
        fixed = text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return text
    return fixed if fixed.count("�") <= text.count("�") else text


def _searchable(value) -> str:
    text = unicodedata.normalize("NFKD", _clean_text(value).lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def _jsonl_file(path=None) -> Path:
    source_path = Path(path or settings.data_dir).resolve()
    if not source_path.is_dir():
        return source_path

    jsonl_files = sorted(source_path.glob("*.jsonl"))
    if len(jsonl_files) == 1:
        return jsonl_files[0]
    if not jsonl_files:
        raise FileNotFoundError(f"No JSONL file found in: {source_path}")
    raise ValueError(f"Multiple JSONL files found in {source_path}; pass one file path explicitly.")


def _display_price(record: dict) -> str:
    price = record.get("price")
    if isinstance(price, (int, float)) and price:
        return f"{price:,.0f} VND"
    return str(record.get("price_raw") or "Not available")


def _spec_lookup(specs_norm: dict, *keywords: str) -> str:
    for key_text, value in specs_norm.items():
        if all(keyword in key_text for keyword in keywords):
            return _clean_text(value)
    return ""


def _floats(pattern: re.Pattern, text: str) -> list[float]:
    return [float(match.replace(",", ".")) for match in pattern.findall(_clean_text(text))]


def _first_float(pattern: re.Pattern, text: str) -> float | None:
    values = _floats(pattern, text)
    return values[0] if values else None


def _max_float(pattern: re.Pattern, text: str) -> float | None:
    values = _floats(pattern, text)
    return max(values) if values else None


def _camera_features(rear_camera: str, front_camera: str) -> dict:
    rear_text = _searchable(rear_camera)
    rear_mp = _max_float(_MP_RE, rear_camera)
    front_mp = _max_float(_MP_RE, front_camera)
    best_aperture = _first_float(_APERTURE_RE, rear_camera)
    has_ois = any(term in rear_text for term in ["ois", "chong rung", "quang hoc"])
    has_telephoto = "telephoto" in rear_text or "zoom" in rear_text
    has_ultrawide = any(term in rear_text for term in ["sieu rong", "ultrawide", "ultra wide"])

    camera_score = 0.0
    if rear_mp:
        camera_score += min(rear_mp, 50) * 0.8
    if front_mp:
        camera_score += min(front_mp, 32) * 0.25
    if best_aperture:
        camera_score += max(0, 2.4 - best_aperture) * 8
    if has_ois:
        camera_score += 18
    if has_telephoto:
        camera_score += 16
    if has_ultrawide:
        camera_score += 12

    return {
        "rear_camera_mp": rear_mp or "",
        "front_camera_mp": front_mp or "",
        "camera_aperture": best_aperture or "",
        "has_ois": has_ois,
        "has_telephoto": has_telephoto,
        "has_ultrawide": has_ultrawide,
        "camera_score": round(min(camera_score, 100), 2),
    }


def _structured_features(record: dict) -> dict:
    specs = record.get("specs_kv") or {}
    if not isinstance(specs, dict):
        specs = {}

    # Normalize keys once to avoid repeated work across multiple lookups.
    specs_norm = {_searchable(key): value for key, value in specs.items()}

    chipset = _spec_lookup(specs_norm, "chipset") or _spec_lookup(specs_norm, "chip")
    ram = _first_float(_GB_RE, _spec_lookup(specs_norm, "ram"))
    storage = _first_float(_GB_RE, _spec_lookup(specs_norm, "nho", "trong"))
    battery = _first_float(_MAH_RE, _spec_lookup(specs_norm, "pin"))
    rear_camera = _spec_lookup(specs_norm, "camera", "sau")
    front_camera = _spec_lookup(specs_norm, "camera", "truoc")
    camera_features = _camera_features(rear_camera, front_camera)

    performance_score = min(float(ram or 0), 16) * 1.5

    return {
        "chipset": chipset,
        "ram_gb": ram or "",
        "storage_gb": storage or "",
        "battery_mah": battery or "",
        "performance_score": round(performance_score, 2) if performance_score else "",
        **camera_features,
    }


def _feature_summary(features: dict) -> str:
    parts = []
    if features.get("chipset"):
        parts.append(
            f"chipset {features['chipset']}"
            f" (performance score {features.get('performance_score') or 'N/A'})"
        )
    if features.get("ram_gb"):
        parts.append(f"RAM {features['ram_gb']} GB")
    if features.get("storage_gb"):
        parts.append(f"storage {features['storage_gb']} GB")
    if features.get("camera_score"):
        camera_bits = [f"camera score {features['camera_score']}"]
        if features.get("rear_camera_mp"):
            camera_bits.append(f"rear {features['rear_camera_mp']} MP")
        if features.get("front_camera_mp"):
            camera_bits.append(f"front {features['front_camera_mp']} MP")
        if features.get("has_ois"):
            camera_bits.append("OIS")
        if features.get("has_telephoto"):
            camera_bits.append("telephoto")
        if features.get("has_ultrawide"):
            camera_bits.append("ultrawide")
        parts.append(", ".join(camera_bits))
    if features.get("battery_mah"):
        parts.append(f"battery {features['battery_mah']} mAh")
    return "; ".join(parts)


def _page_content(record: dict) -> str:
    title = _clean_text(record.get("title") or "Unknown product")
    url = _clean_text(record.get("url") or "")
    identity = [
        f"Product: {title}",
        f"Brand: {_clean_text(record.get('brand') or 'Unknown')}",
        f"Price: {_display_price(record)}",
    ]
    if url:
        identity.append(f"Source URL: {url}")

    blocks = ["\n".join(identity)]
    if record.get("description"):
        blocks.append(f"Description: {_clean_text(record['description'])}")

    rating = record.get("rating")
    reviews_count = record.get("reviews_count")
    if rating or reviews_count:
        blocks.append(
            f"Rating: {rating or 'Not available'}; review count: {reviews_count or 0}"
        )

    features = _structured_features(record)
    summary = _feature_summary(features)
    if summary:
        blocks.append(f"Structured features: {summary}")

    specs = record.get("specs_kv") or {}
    if isinstance(specs, dict):
        blocks.extend(
            f"Specification - {_clean_text(key)}: {_clean_text(value)}"
            for key, value in specs.items()
            if value
        )
    elif record.get("specs"):
        blocks.append(f"Specifications: {_clean_text(record['specs'])}")

    return "\n\n".join(blocks)


class JSONLoader(BaseLoader):
    """Load CellphoneS JSONL product records as LangChain documents."""

    def __init__(self, file_path=None):
        self.file_path = _jsonl_file(file_path)

    def lazy_load(self) -> Iterator[Document]:
        if not self.file_path.exists():
            raise FileNotFoundError(f"JSONL data file not found: {self.file_path}")

        with self.file_path.open("r", encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                record = self._load_record(line, line_number)
                yield self._record_to_document(record, line_number)

    def load(self) -> list[Document]:
        return list(self.lazy_load())

    def _load_record(self, line: str, line_number: int) -> dict:
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in {self.file_path} at line {line_number}."
            ) from exc

    def _record_to_document(self, record: dict, line_number: int) -> Document:
        url = str(record.get("url") or self.file_path)
        metadata = {
            "source": url,
            "file_source": str(self.file_path),
            "line_number": line_number,
            "title": _clean_text(record.get("title") or "Unknown product"),
            "brand": _clean_text(record.get("brand") or ""),
            "price": record.get("price") or "",
            "scraped_at": str(record.get("scraped_at") or ""),
            **_structured_features(record),
        }
        return Document(page_content=_page_content(record), metadata=metadata)
