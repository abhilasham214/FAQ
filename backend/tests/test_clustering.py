import numpy as np
import pytest

from app.clustering.evaluation import evaluate_k_range
from app.clustering.kmeans import KMeansClusterer
from app.clustering.representatives import nearest_to_centroid
from app.clustering.selection import select_best
from app.core.errors import InsufficientTicketsError
from app.schemas.clustering import KResult
from app.schemas.ticket import Ticket
from app.services.clustering_service import cluster_tickets


def blobs(n_clusters: int, per_cluster: int = 10, dim: int = 8) -> np.ndarray:
    """Well-separated clusters: each one lives on its own axis."""
    rng = np.random.default_rng(0)
    points = []
    for c in range(n_clusters):
        center = np.zeros(dim)
        center[c] = 1.0
        points.append(center + rng.normal(0, 0.02, size=(per_cluster, dim)))
    return np.vstack(points)


def test_evaluate_scores_each_k_and_picks_true_k():
    results, fits = evaluate_k_range(blobs(4), KMeansClusterer(), ks=(3, 4, 5))
    assert [r.k for r in results] == [3, 4, 5]
    assert select_best(results).k == 4
    labels, _ = fits[4]
    assert len(set(labels)) == 4


def test_select_best_tie_prefers_smaller_k():
    results = [KResult(k=5, silhouette=0.5), KResult(k=3, silhouette=0.5), KResult(k=4, silhouette=0.4)]
    assert select_best(results).k == 3


def test_insufficient_tickets():
    with pytest.raises(InsufficientTicketsError):
        evaluate_k_range(blobs(3, per_cluster=1), KMeansClusterer(), ks=(3, 4, 5))


def test_nearest_to_centroid_returns_members_only():
    emb = blobs(3)
    labels, centroids = KMeansClusterer().fit(emb, 3)
    for cid in range(3):
        reps = nearest_to_centroid(emb, labels, centroids, cid, top_n=3)
        assert len(reps) == 3
        assert all(labels[i] == cid for i in reps)


def test_cluster_tickets_counts_sum_to_total(fake_embedder):
    themes = {
        "payment pending debited reconciled gateway": "pay",
        "login password session token expired": "auth",
        "refund bank amount account processed": "refund",
    }
    tickets = []
    for phrase in themes:
        for i in range(8):
            n = len(tickets) + 1
            tickets.append(
                Ticket(ticket_id=f"T{n}", title=phrase, description=f"{phrase} case {i}", resolution=phrase, status="resolved")
            )
    result = cluster_tickets(tickets, fake_embedder, KMeansClusterer())
    assert result.chosen_k == 3
    assert sum(c.size for c in result.clusters) == len(tickets)
    all_ids = sorted(tid for c in result.clusters for tid in c.ticket_ids)
    assert all_ids == sorted(t.ticket_id for t in tickets)
    for c in result.clusters:
        assert set(c.representative_ticket_ids) <= set(c.ticket_ids)
