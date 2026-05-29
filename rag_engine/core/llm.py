from rag_engine.core.config import settings
from langchain_ollama import ChatOllama
from functools import lru_cache
import os
from langchain_google_genai import ChatGoogleGenerativeAI



@lru_cache(maxsize=8)
def _get_llm_model(temperature: float, reasoning: bool = False):
    """Get the active LLM model based on configuration."""
    
    if settings.llm_provider == "gemini" and "GOOGLE_API_KEY" in os.environ:
        print(f"Using Gemini model: {settings.llm_model}")
        model = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            temperature=temperature,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            thinking_level='medium' if reasoning else 'low',
        )
        return model
    else:
        print(f"Using Ollama model: {settings.llm_model}")
        model = ChatOllama(
            model=settings.llm_model,
            temperature=temperature,
            reasoning=reasoning
        )
        return model



def _generate_ollama(system_prompt: str, user_prompt: str, temperature: float, reasoning: bool = False) -> str:
    """
    Call local Ollama server and return the generated text.
    
    Args:
        system_prompt (str): The system prompt to send to the LLM.
        user_prompt (str): The user prompt to send to the LLM.
        temperature (float): The sampling temperature for generation.
        reasoning (Optional[bool]): Activate model's reasoning mode.
    
    Returns:
        The generated response text from the LLM.
    """
    llm = _get_llm_model(temperature, reasoning=reasoning)
    
    messages = [
        ('system', system_prompt),
        ('user', user_prompt)
    ]
    response = llm.invoke(messages)
    return response.content.strip()



def _generate_gemini(system_prompt: str, user_prompt: str, temperature: float) -> str:
    """
    Call the configured Gemini model and return generated text.
    
    Args:
        system_prompt: The system prompt to send to the LLM.
        user_prompt: The user prompt to send to the LLM.
        temperature: The sampling temperature for generation.
        
    Returns:
        The generated response text from the LLM.
    """
    if not settings.gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY or GOOGLE_API_KEY is required when LLM_PROVIDER=gemini."
        )

    llm = _get_llm_model(temperature, reasoning=False)
    messages = [
        ("system", system_prompt),
        ("user", user_prompt)
    ]
    response = llm.invoke(messages)
    return response.content.strip()



def generate_response_stream(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    reasoning: bool = False,
):
    """Yield content chunks from the active LLM. Works for both Ollama and Gemini."""
    llm = _get_llm_model(temperature, reasoning=reasoning)
    messages = [("system", system_prompt), ("user", user_prompt)]
    for chunk in llm.stream(messages):
        content = getattr(chunk, "content", "")
        if content:
            yield content


def generate_response(system_prompt: str, user_prompt: str, temperature: float, reasoning: bool = False) -> str:
    """
    Call the active LLM and return the generated text.

    Args:
        system_prompt: The system prompt to send to the LLM.
        user_prompt: The user prompt to send to the LLM.
        temperature: The sampling temperature for generation.
    
    Returns:
        The generated response text from the LLM.
    """
    if settings.llm_provider == 'gemini':
        return _generate_gemini(system_prompt, user_prompt, temperature, reasoning)
    else:
        return _generate_ollama(system_prompt, user_prompt, temperature, reasoning)


def _strip_reasoning(text: str) -> str:
    """Remove <think>...</think> blocks some reasoning models emit."""
    import re
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _extract_json_blob(text: str) -> str:
    """Pull the first {...} JSON object out of a possibly noisy LLM response."""
    import re
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    return match.group(0) if match else ""


def classify_and_rewrite(query: str, history: str = "") -> dict:
    """Single LLM call returning intent, rewritten query, and metadata filters.

    Output schema::

        {
          "intent": "smalltalk" | "product_advice" | "invalid",
          "rewritten": "...",
          "filters": {
              "brand": str?,           # e.g. "Apple", "Samsung"
              "price_min": number?,    # VND
              "price_max": number?,    # VND
              "ram_min": number?,      # GB
              "storage_min": number?,  # GB
              "battery_min": number?,  # mAh
          }
        }

    Falls back to ``product_advice`` + original query + empty filters on any
    parsing failure.
    """
    import json

    system_prompt = f"""
    HISTORY:
    {history}

    TASK:
    1. Base on HISTORY and current QUERY, classify the user question into EXACTLY ONE of: smalltalk, product_advice, invalid. NOTE: some queries are additional information for previous query.
       - smalltalk: greetings, thanks, farewells, or casual conversation.
       - product_advice: asks about, compares, or requests advice on technology products such as phones, laptops, PCs, components, prices, specifications, cameras, batteries, or performance.
       - invalid: empty or completely unrelated.
    2. Rewrite the question as a SHORT, CLEAR, keyword-rich product-search query, at most 25 words, preserving the original meaning.
       - If the intent is NOT product_advice, copy the original question verbatim.
    3. Extract "filters": constraints the user states explicitly. ONLY fill fields the user clearly mentions; omit fields that are not clearly mentioned.
       - brand (string): manufacturer or brand, e.g. "Apple", "Samsung", "Xiaomi", "Oppo", "Vivo", "Realme", "Asus".
       - price_min, price_max (number, VND): "under 20 million VND" means price_max=20000000; "10-15 million VND" means price_min=10000000 and price_max=15000000; "above 30 million VND" means price_min=30000000.
       - ram_min (number, GB): "RAM 8GB or more" means ram_min=8.
       - storage_min (number, GB): "256GB" means storage_min=256.
       - battery_min (number, mAh): "battery 5000 mAh or more" means battery_min=5000.

    OUTPUT REQUIREMENTS:
    - Return ONLY ONE valid JSON object, with NO markdown, NO explanation, and NO extra line breaks.
    - Schema: {{"intent": "smalltalk"|"product_advice"|"invalid", "rewritten": "...", "filters": {{...}}}}
    - "filters" may be an empty object {{}} if there are no constraints.
    """
    fallback = {"intent": "product_advice", "rewritten": query, "filters": {}}

    try:
        raw = generate_response(system_prompt, query, temperature=0.0)
    except Exception:
        return fallback

    blob = _extract_json_blob(_strip_reasoning(raw))
    if not blob:
        return fallback

    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return fallback

    intent = str(data.get("intent", "")).strip().lower()
    if intent not in {"smalltalk", "product_advice", "invalid"}:
        intent = "product_advice"

    rewritten = str(data.get("rewritten", "")).strip().strip('"').strip("'")
    if not rewritten:
        rewritten = query

    raw_filters = data.get("filters") if isinstance(data.get("filters"), dict) else {}
    filters = _sanitize_filters(raw_filters)

    return {"intent": intent, "rewritten": rewritten, "filters": filters}


_NUMERIC_FILTER_KEYS = {"price_min", "price_max", "ram_min", "storage_min", "battery_min"}


def _sanitize_filters(raw: dict) -> dict:
    """Keep only known keys with valid values; coerce numerics; drop empties."""
    out: dict = {}
    brand = raw.get("brand")
    if isinstance(brand, str) and brand.strip():
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


def rewrite_query_for_retrieval(query: str, history: str = "") -> str:
    """Rewrite the user query to be more effective for retrieval.

    Returns the rewritten query, or the original query unchanged on failure.
    """
    system_prompt = f"""
    Conversation history:
    {history}

    SYSTEM PROMPT:
    Based on the conversation history and the user's question, rewrite the question into ONE short, clear, keyword-rich query for searching product documents.

    OUTPUT REQUIREMENTS:
    - Return ONLY the rewritten query, with no explanation, no line breaks, no markdown, and no surrounding quotes.
    - Preserve the original meaning of the question.
    - Use at most 25 words.
    """
    try:
        raw = generate_response(system_prompt, query, temperature=0.1)
    except Exception:
        return query

    rewritten = _strip_reasoning(raw).strip().strip('"').strip("'")
    # Take only the first non-empty line to defend against models that explain.
    rewritten = next((line.strip() for line in rewritten.splitlines() if line.strip()), "")
    return rewritten or query


def classify_intent(query: str, history: str = "") -> str:
    """Classify the user query into ``smalltalk`` | ``product_advice`` | ``invalid``.

    Always returns one of the three exact labels.
    """
    system_prompt = f"""
    HISTORY:
    {history}

    SYSTEM PROMPT:
    Classify the user's question into EXACTLY ONE of these labels:
    - smalltalk: greetings, thanks, or casual conversation.
    - product_advice: asks about, compares, or requests advice on products such as phones, specifications, prices, cameras, batteries, or gaming performance.
    - invalid: empty or completely unrelated to the two categories above.

    OUTPUT REQUIREMENTS:
    - Return ONLY one word from: smalltalk | product_advice | invalid
    - Do not explain, do not add punctuation, and do not add a line break.
    """
    try:
        raw = generate_response(system_prompt, query, temperature=0.0)
    except Exception:
        return "product_advice"

    text = _strip_reasoning(raw).lower()
    # First exact-token match wins.
    for label in ("product_advice", "smalltalk", "invalid"):
        if label in text:
            return label
    return "product_advice"



def summarize_history(history: str, reasoning: bool = False) -> str:
    """
    Summarize the conversation history to make it more concise and user-friendly.
    
    Args:
        history (str): The conversation history to summarize.
        reasoning (Optional[Bool]): Activate model's reasoning mode.
    
    Returns:
        A summarized version of the history.
    """
    
    if not history:
        return ""

    system_prompt = f"""
    SYSTEM PROMPT:
    Summarize the following conversation history in a concise and easy-to-understand way while preserving its main meaning:
    """
    
    return generate_response(system_prompt, history, temperature=0.1, reasoning=reasoning)
