from __future__ import annotations

from typing import Dict, Sequence, Tuple

import numpy as np
from sklearn.metrics import silhouette_score

from app.clustering.base import Clusterer
from app.core.errors import InsufficientTicketsError
from app.schemas.clustering import KResult

DEFAULT_KS = (3, 4, 5)


def evaluate_k_range(
    embeddings: np.ndarray,
    clusterer: Clusterer,
    ks: Sequence[int] = DEFAULT_KS,
) -> Tuple[list[KResult], Dict[int, Tuple[np.ndarray, np.ndarray]]]:
    """Fit `clusterer` for each K and score it with the silhouette score (cosine).

    Returns the scores plus the fitted (labels, centroids) per K so the
    winning fit can be reused without clustering again.
    """
    n = len(embeddings)
    if n <= max(ks):
        raise InsufficientTicketsError(
            f"Need more than {max(ks)} tickets to evaluate K={list(ks)}; got {n}"
        )

    results: list[KResult] = []
    fits: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
    for k in ks:
        labels, centroids = clusterer.fit(embeddings, k)
        if len(set(labels)) < 2:  # silhouette is undefined for a single cluster
            score = -1.0
        else:
            score = float(silhouette_score(embeddings, labels, metric="cosine"))
        results.append(KResult(k=k, silhouette=round(score, 4)))
        fits[k] = (labels, centroids)
    return results, fits
