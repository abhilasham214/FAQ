from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: Optional[str] = None
    database_url: Optional[str] = None
    llm_provider: str = "mock"  # "mock" (offline) or "gemini"
    llm_fallback_to_mock: bool = False  # opt-in: if Gemini fails, write that FAQ with the offline mock instead
    gemini_model: str = "gemini-3.8-flash"
    gemini_timeout_seconds: float = 60.0
    gemini_max_retries: int = 1  # retries after the first attempt, for transient errors only
    gemini_retry_base_delay: float = 1.0
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    cache_dir: str = ".cache"
    cors_origins: str = "http://localhost:3000"  # comma-separated


def get_settings() -> Settings:
    return Settings()
