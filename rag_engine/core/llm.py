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