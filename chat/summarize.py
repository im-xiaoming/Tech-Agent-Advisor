""""Summarize the conversation history for a given user."""

from functools import lru_cache
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from rag_engine.core.config import settings
import torch


@lru_cache(maxsize=1)
def get_classifier():
    tokenizer = AutoTokenizer.from_pretrained("VietAI/vit5-large-vietnews-summarization")  
    model = AutoModelForSeq2SeqLM.from_pretrained("VietAI/vit5-large-vietnews-summarization")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    return model, tokenizer


def summarize_history(history: str) -> str:
    """
    Summarize the conversation history to keep it concise for the prompt.
    
    Args:
        history (str): The raw conversation history.
    
    Returns:
        str: The summarized conversation history.
    """
    if not history:
        return ""
    
    model, tokenizer = get_classifier()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    encoding = tokenizer(history, return_tensors="pt", truncation=True)
    input_ids, attention_masks = encoding["input_ids"].to(device), encoding["attention_mask"].to(device)
    outputs = model.generate(
        input_ids=input_ids, attention_mask=attention_masks,
        max_length=settings.max_length,
        num_beams=settings.beam_size,
        early_stopping=True
    )
    summary = []
    for output in outputs:
        line = tokenizer.decode(output, skip_special_tokens=True, clean_up_tokenization_spaces=True)
        summary.append(line)
    return '\n'.join(summary).strip()
