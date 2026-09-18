from __future__ import annotations

from typing import List, Tuple

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.clustering.base import Clusterer
from app.core.errors import EmptyDatasetError
from app.embeddings.base import EmbeddingProvider
from app.llm.base import LLMProvider
from app.models import Cluster, ClusterRun, ClusterTicket, Faq, TicketRow
from app.schemas.api import StepOut
from app.schemas.clustering import ClusteringResult
from app.schemas.faq import ClusterFaqResult
from app.services.clustering_service import cluster_tickets
from app.services.faq_generation import FaqGenerator
from app.services.ticket_service import ticket_from_row


def generate_knowledge_base(
    db: Session,
    embedder: EmbeddingProvider,
    clusterer: Clusterer,
    llm: LLMProvider,
    cache_dir: str,
) -> Tuple[ClusterRun, List[ClusterFaqResult], List[StepOut]]:
    """Run tickets -> embeddings -> clustering -> FAQs and replace the stored run.

    Clustering errors (too few tickets, embedding failure) abort with an exception.
    FAQ errors never do: they are stored on the affected cluster.
    """
    tickets = [ticket_from_row(r) for r in db.scalars(select(TicketRow).order_by(TicketRow.ticket_id))]
    if not tickets:
        raise EmptyDatasetError("No tickets uploaded yet")
    steps = [StepOut(name="Loaded tickets", status="done", detail=f"{len(tickets)} tickets")]

    clustering = cluster_tickets(tickets, embedder, clusterer)
    steps.append(StepOut(name="Generated embeddings", status="done"))
    steps.append(StepOut(name="Identified clusters", status="done", detail=f"K={clustering.chosen_k}"))

    generator = FaqGenerator(llm, cache_dir)
    faq_results = generator.generate_all(clustering, {t.ticket_id: t for t in tickets})
    failed = sum(1 for r in faq_results if r.faq is None)
    status = "done" if not failed else "failed"
    steps.append(StepOut(name="Generated themes", status=status))
    steps.append(StepOut(name="Generated FAQs", status=status, detail=f"{len(faq_results) - failed} ok, {failed} failed"))

    run = _replace_run(db, clustering, faq_results, len(tickets))
    return run, faq_results, steps


def _replace_run(
    db: Session, clustering: ClusteringResult, faq_results: List[ClusterFaqResult], total: int
) -> ClusterRun:
    """Swap the stored run for the new one in a single transaction."""
    faq_by_cluster = {r.cluster_id: r for r in faq_results}
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
            result = faq_by_cluster.get(info.cluster_id)
            draft = result.faq if result else None
            cluster = Cluster(
                run_id=run.id,
                cluster_index=info.cluster_id,
                name=draft.theme if draft else f"Cluster {info.cluster_id + 1}",
                description=draft.description if draft else "",
                ticket_count=info.size,
                faq_error=None if draft else (result.error if result else "FAQ was not generated"),
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
            if draft:
                db.add(
                    Faq(
                        cluster_id=cluster.id,
                        theme=draft.theme,
                        description=draft.description,
                        question=draft.question,
                        answer=draft.answer,
                        resolution_steps=draft.resolution_steps,
                        source_ticket_ids=draft.source_ticket_ids,
                        insufficient_information=draft.insufficient_information,
                    )
                )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return run
