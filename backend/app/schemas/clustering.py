"""In-memory result of one clustering pass (before it is stored in the database)."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel


class KResult(BaseModel):
    k: int
    silhouette: float


class ClusterInfo(BaseModel):
    cluster_id: int
    size: int
    ticket_ids: List[str]
    representative_ticket_ids: List[str]


class ClusteringResult(BaseModel):
    chosen_k: int
    silhouette: float
    k_results: List[KResult]
    clusters: List[ClusterInfo]
