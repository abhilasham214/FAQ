"""Interface every embedding backend implements."""
from __future__ import annotations

from typing import List, Protocol

import numpy as np


class EmbeddingProvider(Protocol):
    """Anything that turns texts into an (n, dim) array of L2-normalised vectors."""

    name: str

    def embed(self, texts: List[str]) -> np.ndarray: ...
