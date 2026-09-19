"""K-Means implementation of the Clusterer protocol (scikit-learn)."""
from __future__ import annotations

import numpy as np
from sklearn.cluster import KMeans


class KMeansClusterer:
    def __init__(self, random_state: int = 42) -> None:
        self._random_state = random_state

    def fit(self, embeddings: np.ndarray, n_clusters: int):
        # Fixed seed + 10 restarts: the same tickets always give the same clusters, which keeps
        # results reproducible and lets the LLM cache hit on re-runs.
        model = KMeans(n_clusters=n_clusters, n_init=10, random_state=self._random_state)
        labels = model.fit_predict(embeddings)
        return labels, model.cluster_centers_
