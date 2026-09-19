"""Interface every clustering algorithm implements (only K-Means today)."""
from __future__ import annotations

from typing import Protocol

import numpy as np


class Clusterer(Protocol):
    """A clustering algorithm. HDBSCAN can implement this later.

    `fit` returns (labels, centroids); centroids has shape (n_clusters, dim).
    """

    def fit(self, embeddings: np.ndarray, n_clusters: int) -> "tuple[np.ndarray, np.ndarray]": ...
