from functools import lru_cache
import re
from typing import Any, Callable

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from rag_engine.core.config import settings


_Message = tuple[str, str]
_ModelFactory = Callable[[str, float, bool], Any]

_NUMERIC_FILTER_KEYS = {"price_min", "price_max", "ram_min", "storage_min", "battery_min"}

# Words the LLM sometimes mislabels as a "brand" but that match no product's
# metadata.brand (they are operating systems, form factors, or generic terms).
# Treating them as a brand filter wrongly zeroes out retrieval, so drop them and
# let semantic search handle the intent instead.
_NON_BRAND_WORDS = {
    "android",
    "ios",
    "iphoneos",
    "ipados",
    "windows",
    "macos",
    "harmonyos",
    "smartphone",
    "phone",
    "điện thoại",
    "laptop",
    "tablet",
    "máy tính",
}


def _build_messages(system_prompt: str, user_prompt: str) -> list[_Message]:
    """Build the standard LangChain chat message payload."""
    return [("system", system_prompt), ("user", user_prompt)]


def _response_content(response, *, strip: bool = True) -> str:
    """Extract plain text content from a LangChain chat response."""
    content = getattr(response, "content", "")
    if isinstance(content, list):
        text = "".join(
            str(item.get("text", item)) if isinstance(item, dict) else str(item)
            for item in content
        )
    else:
        text = str(content)
    return text.strip() if strip else text


def _build_gemini_model(model_name: str, temperature: float, reasoning: bool):
    """Create a Gemini chat model instance."""
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        thinking_level="medium" if reasoning else "low",
    )


def _build_openai_model(model_name: str, temperature: float, reasoning: bool):
    """Create an OpenAI chat model instance."""
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        stream_usage=True,
        max_tokens=None,
        timeout=None,
        reasoning_effort="medium" if reasoning else "low",
        max_retries=2,
    )


def _build_ollama_model(model_name: str, temperature: float, reasoning: bool):
    """Create an Ollama chat model instance."""
    return ChatOllama(
        model=model_name,
        temperature=temperature,
        reasoning=reasoning,
    )


_MODEL_FACTORIES: dict[str, _ModelFactory] = {
    "gemini": _build_gemini_model,
    "openai": _build_openai_model,
    "ollama": _build_ollama_model,
}

_PROVIDER_LABELS = {
    "gemini": "Gemini",
    "openai": "OpenAI",
    "ollama": "Ollama",
}

_REQUIRED_PROVIDER_KEYS = {
    "gemini": (
        settings.gemini_api_key,
        "GEMINI_API_KEY or GOOGLE_API_KEY is required when LLM_PROVIDER=gemini.",
    ),
    "openai": (
        settings.openai_api_key,
        "OPENAI_API_KEY is required when LLM_PROVIDER=openai.",
    ),
}


def _active_provider() -> str:
    """Return the configured provider, falling back to Ollama for unknown values."""
    return settings.llm_provider if settings.llm_provider in _MODEL_FACTORIES else "ollama"


def _validate_provider_credentials(provider: str) -> None:
    """Raise when the configured provider is missing required credentials."""
    required = _REQUIRED_PROVIDER_KEYS.get(provider)
    if not required:
        return

    api_key, error_message = required
    if not api_key:
        raise ValueError(error_message)


@lru_cache(maxsize=8)
def _get_llm_model(
    temperature: float,
    reasoning: bool = False,
    model_name: str | None = None,
):
    """Get the active LLM model based on configuration."""
    provider = _active_provider()
    active_model = model_name or settings.llm_model
    _validate_provider_credentials(provider)
    print(f"Using {_PROVIDER_LABELS[provider]} model: {active_model}")
    return _MODEL_FACTORIES[provider](active_model, temperature, reasoning)


def _invoke_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    reasoning: bool = False,
    model_name: str | None = None,
) -> str:
    """Invoke the active chat model and return stripped response content."""
    llm = _get_llm_model(temperature, reasoning=reasoning, model_name=model_name)
    response = llm.invoke(_build_messages(system_prompt, user_prompt))
    return _response_content(response)


def _stream_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    reasoning: bool = False,
    model_name: str | None = None,
):
    """Yield content chunks from the active chat model without trimming whitespace."""
    llm = _get_llm_model(temperature, reasoning=reasoning, model_name=model_name)
    for chunk in llm.stream(_build_messages(system_prompt, user_prompt)):
        content = _response_content(chunk, strip=False)
        if content:
            yield content


def _strip_reasoning(text: str) -> str:
    """Remove <think>...</think> blocks some reasoning models emit."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _extract_json_blob(text: str) -> str:
    """Pull the first {...} JSON object out of a possibly noisy LLM response."""
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    return match.group(0) if match else ""


def _sanitize_filters(raw: dict) -> dict:
    """Keep only known keys with valid values; coerce numerics; drop empties."""
    out: dict = {}
    brand = raw.get("brand")
    if isinstance(brand, str) and brand.strip():
        if brand.strip().lower() not in _NON_BRAND_WORDS:
            out["brand"] = brand.strip()
    for key in _NUMERIC_FILTER_KEYS:
        value = raw.get(key)
        if value is None or value == "":
            continue
        try:
            out[key] = float(value)
        except (TypeError, ValueError):
            continue
    return out
