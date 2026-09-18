from __future__ import annotations

import hashlib
from typing import List

import numpy as np
import pytest


class FakeEmbedder:
    """Deterministic, model-free embedder: hashed bag-of-words, L2-normalised."""

    name = "fake"

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim
        self.calls = 0

    def embed(self, texts: List[str]) -> np.ndarray:
        self.calls += 1
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in text.lower().split():
                idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim
                out[i, idx] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()
