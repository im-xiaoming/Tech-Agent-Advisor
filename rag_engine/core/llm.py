from rag_engine.core.config import settings
from ollama import chat


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


def generate_response(system_prompt: str, user_prompt: str, temperature: float) -> str:
    """
    Call local Ollama server and return the generated text.
    
    Args:
        system_prompt: The system prompt to send to the LLM.
        user_prompt: The user prompt to send to the LLM.
        temperature: The sampling temperature for generation.
    
    Returns:
        The generated response text from the LLM.
    """
    # provider = (settings.llm_provider or "ollama").lower()
    return _generate_ollama(system_prompt, user_prompt, temperature)


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
    return generate_response(system_prompt, query, temperature=0.1)