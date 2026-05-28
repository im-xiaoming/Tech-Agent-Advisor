from rag_engine.core.config import settings
from langchain_ollama import ChatOllama
from functools import lru_cache
import os
from langchain_google_genai import ChatGoogleGenerativeAI



@lru_cache(maxsize=1)
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


def rewrite_query_for_retrieval(query: str, history: str = "") -> str:
    """Rewrite the user query to be more effective for retrieval.

    Returns the rewritten query, or the original query unchanged on failure.
    """
    system_prompt = f"""
    Lịch sử trò chuyện:
    {history}

    SYSTEM PROMPT:
    Dựa vào lịch sử trò chuyện và câu hỏi của người dùng, hãy viết lại câu hỏi này thành MỘT câu truy vấn ngắn gọn, rõ ràng, giàu từ khóa, để tìm kiếm tài liệu sản phẩm.

    YÊU CẦU OUTPUT:
    - CHỈ trả về duy nhất câu truy vấn đã viết lại, không thêm giải thích, không xuống dòng, không markdown, không đặt trong dấu ngoặc.
    - Giữ nguyên ý nghĩa câu hỏi gốc.
    - Tối đa 25 từ.
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
    Phân loại câu hỏi của người dùng vào ĐÚNG MỘT trong ba nhãn:
    - smalltalk: chào hỏi, cảm ơn, trò chuyện phiếm.
    - product_advice: hỏi/so sánh/tư vấn về sản phẩm (điện thoại, cấu hình, giá, camera, pin, hiệu năng chơi game, v.v.).
    - invalid: câu rỗng hoặc hoàn toàn không liên quan đến hai loại trên.

    YÊU CẦU OUTPUT:
    - CHỈ trả về duy nhất một từ trong: smalltalk | product_advice | invalid
    - Không giải thích, không thêm dấu câu, không xuống dòng.
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



def summarize_history(history: str, reasoning: bool = True) -> str:
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
    Hãy tóm tắt đoạn lịch sử trò chuyện sau đây một cách ngắn gọn và dễ hiểu hơn, đồng thời giữ nguyên ý nghĩa chính của nó:
    """
    
    return generate_response(system_prompt, history, temperature=0.1, reasoning=reasoning)
