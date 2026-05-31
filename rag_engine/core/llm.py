from rag_engine.core.llm_utils import (
    _extract_json_blob,
    _invoke_llm,
    _sanitize_filters,
    _stream_llm,
    _strip_reasoning,
)


def generate_response_stream(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    reasoning: bool = False,
):
    """Yield content chunks from the active LLM."""
    yield from _stream_llm(
        system_prompt,
        user_prompt,
        temperature,
        reasoning=reasoning,
    )


def generate_response(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    reasoning: bool = False,
) -> str:
    """
    Call the active LLM and return the generated text.

    Args:
        system_prompt: The system prompt to send to the LLM.
        user_prompt: The user prompt to send to the LLM.
        temperature: The sampling temperature for generation.

    Returns:
        The generated response text from the LLM.
    """
    return _invoke_llm(system_prompt, user_prompt, temperature, reasoning=reasoning)


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

    system_prompt = f"""You triage turns for a Vietnamese tech-shopping assistant and return ONE JSON object.

CONVERSATION HISTORY (context for resolving references; do not answer it):
{history}

For the current QUERY, produce three fields.

1. "intent" — exactly one of:
   - "smalltalk": greetings, thanks, farewells, casual chit-chat.
   - "product_advice": any request about tech products (phones, laptops, PCs, keyboards, mice, headphones, components, specs, prices, cameras, batteries, performance, comparisons). This INCLUDES short, terse, or colloquial follow-ups, corrections, and refinements (e.g. "nó giá bao nhiêu", "k chọn bàn phím mà", "loại rẻ hơn", "cái nào mạnh hơn").
   - "invalid": empty input, or clearly unrelated to tech shopping (e.g. weather, jokes).
   If torn between "invalid" and "product_advice", choose "product_advice".

2. "rewritten" — a self-contained Vietnamese product-search query (<=25 words) that still makes sense WITHOUT the history:
   - If intent is not product_advice, copy QUERY verbatim.
   - Resolve every reference ("nó", "cái đó", "cái kia", "máy này", "this one"…) to the full product name from HISTORY.
   - If QUERY names no product but recent HISTORY is about a product category, keep that category (e.g. after discussing keyboards, "làm văn phòng thì chọn cái nào" → "bàn phím cho văn phòng").
   - For a correction of product type, keep the corrected type and drop the wrong one.
   - For a comparison, name EVERY product on both sides in full, including ones from earlier turns. Never drop a side.

3. "filters" — only constraints the user states explicitly; omit anything unstated:
   - "brand" (str): a real manufacturer (Apple, Samsung, Xiaomi, Oppo…). Never use an operating system or generic word (android, ios, smartphone, điện thoại) as a brand.
   - "price_min" / "price_max" (VND): "dưới 20 triệu" → price_max=20000000; "10-15 triệu" → price_min=10000000, price_max=15000000; "trên 30 triệu" → price_min=30000000.
   - "ram_min" (GB), "storage_min" (GB), "battery_min" (mAh).

Output ONLY the JSON object, no markdown and no commentary:
{{"intent": "...", "rewritten": "...", "filters": {{...}}}}
Use {{}} for filters when there are none."""
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

    user_prompt = f"""
    HISTORY:
    {history}
    
    USER PROMPT:
    Your task is to summarize the given conversation history in a concise, clear, and easy-to-understand way while preserving the main meaning, important context, decisions, and relevant details.

    Requirements:
    - Clearly separate SYSTEM messages and USER messages.
    - Keep the chronological flow of the conversation.
    - Preserve important technical details, user preferences, constraints, and conclusions.
    - Remove unnecessary repetition, filler text, and small talk.
    - Use simple and readable language.
    - Do not invent or assume information that is not present in the conversation.
    - If the conversation contains multiple topics, group them logically
    - Always summarize in English.
    """
    
    return generate_response("", user_prompt, temperature=0.1, reasoning=reasoning)
