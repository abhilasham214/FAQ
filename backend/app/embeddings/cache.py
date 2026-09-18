from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List

import numpy as np

from app.embeddings.base import EmbeddingProvider


class CachedEmbedder:
    """Wraps an EmbeddingProvider with a per-text on-disk cache.

    Key = sha256(model name + text), so changing the model or the text
    invalidates automatically. Only cache misses reach the wrapped provider.
    """

    def __init__(self, provider: EmbeddingProvider, cache_dir: str) -> None:
        self._provider = provider
        self.name = provider.name
        self._dir = Path(cache_dir) / "embeddings"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, text: str) -> Path:
        key = hashlib.sha256(f"{self.name}\n{text}".encode("utf-8")).hexdigest()
        return self._dir / f"{key}.npy"

    def embed(self, texts: List[str]) -> np.ndarray:
        vectors: list = [None] * len(texts)
        missing: list[int] = []
        for i, text in enumerate(texts):
            path = self._path(text)
            if path.exists():
                try:
                    vectors[i] = np.load(path)
                    continue
                except Exception:  # corrupt cache entry -> recompute
                    pass
            missing.append(i)

        if missing:
            fresh = self._provider.embed([texts[i] for i in missing])
            for i, vec in zip(missing, fresh):
                vectors[i] = vec
                np.save(self._path(texts[i]), vec)

        return np.vstack(vectors) if vectors else np.zeros((0, 0), dtype=np.float32)
