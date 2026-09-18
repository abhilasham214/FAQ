from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: Optional[str] = None
    database_url: Optional[str] = None
    llm_provider: str = "mock"  # "mock" (offline) or "gemini"
    gemini_model: str = "gemini-2.5-flash"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    cache_dir: str = ".cache"
    cors_origins: str = "http://localhost:3000"  # comma-separated


def get_settings() -> Settings:
    return Settings()
