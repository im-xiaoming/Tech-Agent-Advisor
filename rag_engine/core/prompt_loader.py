from pathlib import Path
from typing import Tuple
from rag_engine.core.config import settings


def load_prompt(prompt_path: str | Path) -> str:
    """
    Load prompt template from a file path or default config.
    
    Args:
        prompt_path (str | Path): The path to the prompt template file.
    
    Returns:
        str: The content of the prompt template.
    """

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def load_advisor_prompt() -> Tuple[str, str]:
    """Load system and user prompts for the advisor agent from the specified filename.

    Returns:
        Tuple[str, str]: The system prompt and user prompt.
    """
    system_prompt_path = settings.prompt_path / "advisor" / "system_prompt.txt"
    user_prompt_path = settings.prompt_path / "advisor" / "user_prompt.txt"
    system_prompt = load_prompt(system_prompt_path)
    user_prompt = load_prompt(user_prompt_path)
    return system_prompt, user_prompt


def load_smalltalk_prompt() -> Tuple[str, str]:
    """Load system and user prompts for the smalltalk agent from the specified filename.

    Returns:
        Tuple[str, str]: The system prompt and user prompt.
    """
    system_prompt_path = settings.prompt_path / "smalltalk" / "system_prompt.txt"
    user_prompt_path = settings.prompt_path / "smalltalk" / "user_prompt.txt"
    system_prompt = load_prompt(system_prompt_path)
    user_prompt = load_prompt(user_prompt_path)
    return system_prompt, user_prompt