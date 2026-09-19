"""Pipeline steps 3-5: embed tickets, cluster for each K, keep the best, pick representatives.

Pure function of its inputs (no database, no LLM), so it can be run and debugged on its own:
  python backend/scripts/run_pipeline.py data/sample_tickets.csv
"""
from __future__ import annotations

from typing import List, Sequence

from app.clustering.base import Clusterer
from app.clustering.evaluation import DEFAULT_KS, evaluate_k_range
from app.clustering.representatives import nearest_to_centroid
from app.clustering.selection import select_best
from app.embeddings.base import EmbeddingProvider
from app.schemas.clustering import ClusteringResult, ClusterInfo
from app.schemas.ticket import Ticket
from app.services.preprocessing import ticket_to_text


def cluster_tickets(
    tickets: List[Ticket],
    embedder: EmbeddingProvider,
    clusterer: Clusterer,
    ks: Sequence[int] = DEFAULT_KS,
    representatives_per_cluster: int = 5,
) -> ClusteringResult:
    """tickets -> text -> embeddings -> try each K -> pick best silhouette -> describe clusters."""
    embeddings = embedder.embed([ticket_to_text(t) for t in tickets])
    k_results, fits = evaluate_k_range(embeddings, clusterer, ks)
    best = select_best(k_results)
    labels, centroids = fits[best.k]

    clusters: list[ClusterInfo] = []
    for cluster_id in range(best.k):
        member_idx = [i for i, label in enumerate(labels) if label == cluster_id]
        rep_idx = nearest_to_centroid(embeddings, labels, centroids, cluster_id, representatives_per_cluster)
        clusters.append(
            ClusterInfo(
                cluster_id=cluster_id,
                size=len(member_idx),
                ticket_ids=[tickets[i].ticket_id for i in member_idx],
                representative_ticket_ids=[tickets[i].ticket_id for i in rep_idx],
            )
        )
    return ClusteringResult(
        chosen_k=best.k, silhouette=best.silhouette, k_results=k_results, clusters=clusters
    )
