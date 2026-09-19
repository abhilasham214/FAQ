"""Choose the tickets sent to the LLM: the ones closest to their cluster's centre."""
from __future__ import annotations

from typing import List

import numpy as np


def nearest_to_centroid(
    embeddings: np.ndarray,
    labels: np.ndarray,
    centroids: np.ndarray,
    cluster_id: int,
    top_n: int = 5,
) -> List[int]:
    """Indices of the `top_n` members closest (cosine) to the cluster centroid."""
    members = np.where(labels == cluster_id)[0]
    centroid = centroids[cluster_id]
    norm = np.linalg.norm(centroid)
    centroid = centroid / norm if norm else centroid
    member_vecs = embeddings[members]
    member_norms = np.linalg.norm(member_vecs, axis=1)
    member_norms[member_norms == 0] = 1.0
    similarity = (member_vecs / member_norms[:, None]) @ centroid
    order = np.argsort(-similarity, kind="stable")[:top_n]
    return [int(members[i]) for i in order]
