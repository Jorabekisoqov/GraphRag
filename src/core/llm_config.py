"""Shared LLM configuration using DeepSeek (OpenAI-compatible API)."""
import os
from langchain_openai import ChatOpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"


def get_llm(
    temperature: float = 0,
    model: str | None = None,
    max_tokens: int | None = None,
    **kwargs,
) -> ChatOpenAI:
    """
    Create a ChatOpenAI client configured for DeepSeek API.

    Uses DEEPSEEK_API_KEY from environment. DeepSeek API is OpenAI-compatible.
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY is not set. Add it to your .env file."
        )
    return ChatOpenAI(
        base_url=DEEPSEEK_BASE_URL,
        api_key=api_key,
        model=model or DEEPSEEK_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
