"""Gemini model configuration."""

import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

DEFAULT_MODEL = "gemini-2.5-flash"


class LLMConfigError(RuntimeError):
    """Raised when the LLM cannot be configured (e.g. missing API key)."""


def get_llm():
    """Return the configured chat model (Gemini by default, DeepSeek optional)."""
    if os.getenv("LLM_PROVIDER", "gemini").lower() == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise LLMConfigError("DEEPSEEK_API_KEY is not set. Please add it to your .env file.")
        from langchain_deepseek import ChatDeepSeek

        return ChatDeepSeek(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            temperature=0,
            api_key=api_key,
            timeout=30,
            max_retries=1,
        )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise LLMConfigError("GEMINI_API_KEY is not set. Please add it to your .env file.")

    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
        temperature=0,
        google_api_key=api_key,
        timeout=30,
        max_retries=1,
    )