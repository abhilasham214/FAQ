from __future__ import annotations

from typing import List, Tuple

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.clustering.base import Clusterer
from app.core.errors import EmptyDatasetError
from app.embeddings.base import EmbeddingProvider
from app.models import Cluster, ClusterRun, ClusterTicket, Faq, TicketRow
from app.schemas.api import StepOut
from app.schemas.clustering import ClusteringResult
from app.services.clustering_service import cluster_tickets
from app.services.ticket_service import ticket_from_row


def build_clusters(
    db: Session,
    embedder: EmbeddingProvider,
    clusterer: Clusterer,
) -> Tuple[ClusterRun, List[StepOut]]:
    """Run tickets -> embeddings -> clustering and replace the stored run.

    Deliberately does NOT call the LLM: clustering is free and deterministic, while FAQ
    generation spends API quota, so it is a separate, explicit step. The clusters this
    produces are fully usable on their own when the LLM provider is unavailable.
    """
    tickets = [ticket_from_row(r) for r in db.scalars(select(TicketRow).order_by(TicketRow.ticket_id))]
    if not tickets:
        raise EmptyDatasetError("No tickets uploaded yet")
    steps = [StepOut(name="Loaded tickets", status="done", detail=f"{len(tickets)} tickets")]

    clustering = cluster_tickets(tickets, embedder, clusterer)
    steps.append(StepOut(name="Generated embeddings", status="done"))
    steps.append(StepOut(name="Identified clusters", status="done", detail=f"K={clustering.chosen_k}"))

    run = _replace_run(db, clustering, len(tickets))
    return run, steps


def _replace_run(db: Session, clustering: ClusteringResult, total: int) -> ClusterRun:
    """Swap the stored run for the new one in a single transaction."""
    try:
        # delete children explicitly: bulk deletes skip ORM cascades
        db.execute(delete(Faq))
        db.execute(delete(ClusterTicket))
        db.execute(delete(Cluster))
        db.execute(delete(ClusterRun))

        run = ClusterRun(
            chosen_k=clustering.chosen_k,
            silhouette=clustering.silhouette,
            k_results=[r.model_dump() for r in clustering.k_results],
            total_tickets=total,
        )
        db.add(run)
        db.flush()

        for info in clustering.clusters:
            cluster = Cluster(
                run_id=run.id,
                cluster_index=info.cluster_id,
                name=f"Cluster {info.cluster_id + 1}",  # replaced by the FAQ theme once one is generated
                description="",
                ticket_count=info.size,
                faq_error=None,
            )
            db.add(cluster)
            db.flush()
            ranks = {tid: rank for rank, tid in enumerate(info.representative_ticket_ids)}
            db.add_all(
                ClusterTicket(
                    cluster_id=cluster.id, ticket_id=tid, is_representative=tid in ranks, rank=ranks.get(tid, 0)
                )
                for tid in info.ticket_ids
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return run
