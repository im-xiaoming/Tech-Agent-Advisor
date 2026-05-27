from pathlib import types
from rag_engine.core.config import settings
from ollama import chat
from google import genai



def _generate_ollama(system_prompt: str, user_prompt: str, temperature: float) -> str:
    """
    Call local Ollama server and return the generated text.
    
    Args:
        system_prompt: The system prompt to send to the LLM.
        user_prompt: The user prompt to send to the LLM.
        temperature: The sampling temperature for generation.
    
    Returns:
        The generated response text from the LLM.
    """

    response = chat(
        model=settings.ollama_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        stream=False,
        think=False,
        options={
            "temperature": temperature,
        }
    )
    return response.message.content.strip()


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

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
        ),
    )
    return (response.text or "").strip()




def _active_model_name() -> str:
    """Get the name of the active LLM model based on the configuration."""
    if settings.llm_provider == "gemini":
        return _generate_gemini
    return _generate_ollama



def generate_response(system_prompt: str, user_prompt: str, temperature: float) -> str:
    """
    Call the active LLM and return the generated text.

    Args:
        system_prompt: The system prompt to send to the LLM.
        user_prompt: The user prompt to send to the LLM.
        temperature: The sampling temperature for generation.
    
    Returns:
        The generated response text from the LLM.
    """
    llm = _active_model_name()
    return llm(system_prompt, user_prompt, temperature)


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
    Dựa vào lịch sử trò chuyện và câu hỏi của người dùng, hãy viết lại câu hỏi theo cách rõ ràng, dễ hiểu hơn, để {settings.ollama_model} có thể hiểu được nhưng vẫn giữ nguyên ý nghĩa. Câu hỏi sẽ được sử dụng để tìm kiếm tài liệu liên quan trong cơ sở dữ liệu, vì vậy hãy đảm bảo rằng nó chứa các từ khóa quan trọng và được diễn đạt một cách chính xác.
    """
    
    llm = _active_model_name()
    return llm(system_prompt, query, temperature=0.1)


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
    
    llm = _active_model_name()
    return llm(system_prompt, query, temperature=0.1)



def summarize_history(history: str) -> str:
    """
    Summarize the conversation history to make it more concise and user-friendly.
    
    Args:
        history (str): The conversation history to summarize.
    
    Returns:
        A summarized version of the history.
    """
    
    if not history:
        return ""

    system_prompt = f"""
    SYSTEM PROMPT:
    Hãy tóm tắt đoạn lịch sử trò chuyện sau đây một cách ngắn gọn và dễ hiểu hơn, đồng thời giữ nguyên ý nghĩa chính của nó:
    """
    llm = _active_model_name()
    return llm(system_prompt, history, temperature=0.1)