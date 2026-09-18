from __future__ import annotations

from typing import List

import numpy as np

from app.core.errors import EmbeddingError


class SentenceTransformerEmbedder:
    """Local embeddings via sentence-transformers (default: all-MiniLM-L6-v2)."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.name = model_name
        self._model = None  # loaded lazily so importing this module stays cheap

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.name)
            except Exception as exc:
                raise EmbeddingError(f"Could not load embedding model '{self.name}': {exc}") from exc
        return self._model

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        model = self._load()
        try:
            vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        except Exception as exc:
            raise EmbeddingError(f"Embedding generation failed: {exc}") from exc
        return np.asarray(vectors, dtype=np.float32)
