from __future__ import annotations

from functools import lru_cache

from app.clustering.base import Clusterer
from app.clustering.kmeans import KMeansClusterer
from app.core.config import get_settings
from app.embeddings.base import EmbeddingProvider
from app.embeddings.cache import CachedEmbedder
from app.embeddings.sentence_transformer import SentenceTransformerEmbedder
from app.llm.base import LLMProvider
from app.llm.fallback import FallbackLLMProvider
from app.llm.gemini import GeminiProvider
from app.llm.mock import MockLLMProvider


@lru_cache
def get_embedder() -> EmbeddingProvider:
    settings = get_settings()
    return CachedEmbedder(SentenceTransformerEmbedder(settings.embedding_model), settings.cache_dir)


def get_clusterer() -> Clusterer:
    return KMeansClusterer()


def get_llm() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "gemini":
        gemini = GeminiProvider(
            settings.gemini_api_key or "",
            settings.gemini_model,
            timeout_seconds=settings.gemini_timeout_seconds,
            max_retries=settings.gemini_max_retries,
            base_delay=settings.gemini_retry_base_delay,
        )
        return FallbackLLMProvider(gemini, MockLLMProvider()) if settings.llm_fallback_to_mock else gemini
    return MockLLMProvider()


def get_cache_dir() -> str:
    return get_settings().cache_dir
