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


def rewrite_query_for_retrieval(query: str, history: str = "") -> str:
    """
    Rewrite the user query to be more effective for retrieval.
    
    Args:
        query: The original user query.
    
    Returns:
        The rewritten query optimized for retrieval.
    """
    
    system_prompt = f"""
    Lịch sử trò chuyện:
    {history}
    
    SYSTEM PROMPT:
    Dựa vào lịch sử trò chuyện và câu hỏi của người dùng, hãy viết lại câu hỏi theo cách rõ ràng, dễ hiểu hơn, để {settings.llm_model} có thể hiểu được nhưng vẫn giữ nguyên ý nghĩa. Câu hỏi sẽ được sử dụng để tìm kiếm tài liệu liên quan trong cơ sở dữ liệu, vì vậy hãy đảm bảo rằng nó chứa các từ khóa quan trọng và được diễn đạt một cách chính xác.
    """
    
    return generate_response(system_prompt, query, temperature=0.1)


def classify_intent(query: str, history: str = "") -> str:
    """
    Classify the user query into one of the predefined intent categories.
    
    Args:
        query (str): The user query to classify.
        history (str, optional): The conversation history.
    
    Returns:
        The predicted intent category (e.g., "smalltalk", "product_advice", "invalid").
    """

    system_prompt = f"""
    HISTORY:
    {history}
    
    SYSTEM PROMPT:
    Dựa vào lịch sử trò chuyện và câu hỏi của người dùng, hãy phân loại câu hỏi này vào một trong các danh mục sau: "smalltalk", "product_advice", "invalid".
    """
    
    return generate_response(system_prompt, query, temperature=0.1)



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
