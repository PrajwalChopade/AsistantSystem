"""
LLM module with document-grounded generation.
"""

from app.llm.models import (
    BaseLLM,
    OpenRouterLLM,
    GeminiLLM,
    DOCUMENT_GROUNDED_SYSTEM_PROMPT,
)
from app.llm.fallback import (
    LLMFallbackChain,
    get_llm,
    generate_response,
)

__all__ = [
    "BaseLLM",
    "OpenRouterLLM",
    "GeminiLLM",
    "DOCUMENT_GROUNDED_SYSTEM_PROMPT",
    "LLMFallbackChain",
    "get_llm",
    "generate_response",
]
