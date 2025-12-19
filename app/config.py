"""
Central configuration for the Document-Driven Support Platform.
All settings loaded from environment with safe defaults.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings with environment variable loading."""
    
    # === Environment ===
    ENV: str = Field(default="development", description="Environment: development, staging, production")
    DEBUG: bool = Field(default=False)
    
    # === API Keys ===
    GEMINI_API_KEY: Optional[str] = Field(default=None)
    OPENROUTER_API_KEY: Optional[str] = Field(default=None)
    LANGSMITH_API_KEY: Optional[str] = Field(default=None)
    
    # === LangSmith Tracing ===
    LANGCHAIN_TRACING_V2: bool = Field(default=False)
    LANGCHAIN_PROJECT: str = Field(default="ai-support-platform")
    LANGCHAIN_ENDPOINT: str = Field(default="https://api.smith.langchain.com")
    
    # === Redis Configuration ===
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    REDIS_PASSWORD: Optional[str] = Field(default=None)
    CACHE_TTL_SECONDS: int = Field(default=3600, description="Default cache TTL: 1 hour")
    
    # === Paths ===
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    DATA_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "data")
    DOCUMENTS_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "data" / "documents")
    VECTORSTORE_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "data" / "vectorstores")
    
    # === Embedding Model ===
    EMBEDDING_MODEL_NAME: str = Field(default="all-MiniLM-L6-v2")
    EMBEDDING_DIMENSION: int = Field(default=384)
    
    # === RAG Configuration ===
    CHUNK_SIZE: int = Field(default=500)
    CHUNK_OVERLAP: int = Field(default=50)
    RETRIEVAL_TOP_K: int = Field(default=3)
    SIMILARITY_THRESHOLD: float = Field(default=0.5, description="Minimum similarity for valid retrieval")
    
    # === LLM Configuration ===
    LLM_TEMPERATURE: float = Field(default=0.1, description="Low temperature for deterministic responses")
    LLM_MAX_TOKENS: int = Field(default=512)
    MAX_ANSWER_LENGTH: int = Field(default=1000, description="Maximum answer character length")
    
    # === Intent & Escalation ===
    ESCALATION_CONFIDENCE_THRESHOLD: float = Field(default=0.75)
    CLARIFICATION_CONFIDENCE_THRESHOLD: float = Field(default=0.4)
    
    # === OpenRouter ===
    OPENROUTER_URL: str = Field(default="https://openrouter.ai/api/v1/chat/completions")
    OPENROUTER_MODEL: str = Field(default="mistralai/mixtral-8x7b-instruct")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Singleton instance
settings = Settings()


def ensure_directories():
    """Create required directories if they don't exist."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    settings.VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)
