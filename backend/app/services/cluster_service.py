"""Read-side queries (clusters, tickets, stats) and the FAQ generate / regenerate actions.

FAQ failures are stored on the cluster as `faq_error` (the user-facing message) rather than
in a status column; _faq_status derives GENERATION_FAILED / QUOTA_EXHAUSTED from it.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import FaqAlreadyExistsError, FaqRegenerationError, NotFoundError
from app.llm.base import LLMProvider
from app.models import Cluster, ClusterRun, ClusterTicket, Faq, FaqStatus, TicketRow
from app.schemas.api import ClusterDetailOut, ClusterListOut, ClusterOut, FaqBatchOut, FaqOut, RunOut, StatsOut
from app.schemas.faq import FaqDraft
from app.schemas.ticket import Ticket
from app.services.faq_generation import (
    GENERATION_FAILED,
    MSG_QUOTA_EXHAUSTED,
    QUOTA_EXHAUSTED,
    FaqGenerator,
)
from app.services.ticket_service import ticket_from_row

# The stored `faq_error` text is the only record of why generation failed (no schema
# change), so map the known message back to its status; anything else is a plain failure.
_STATUS_BY_ERROR = {MSG_QUOTA_EXHAUSTED: QUOTA_EXHAUSTED}


def _faq_status(cluster: Cluster) -> Optional[str]:
    if cluster.faq is not None:
        return cluster.faq.status
    if cluster.faq_error:
        return _STATUS_BY_ERROR.get(cluster.faq_error, GENERATION_FAILED)
    return None  # clustered, no FAQ attempted yet


def _latest_run(db: Session) -> Optional[ClusterRun]:
    return db.scalar(select(ClusterRun).order_by(ClusterRun.id.desc()))


def _representatives(db: Session, cluster_id: int) -> List[Ticket]:
    rows = db.scalars(
        select(TicketRow)
        .join(ClusterTicket, ClusterTicket.ticket_id == TicketRow.ticket_id)
        .where(ClusterTicket.cluster_id == cluster_id, ClusterTicket.is_representative.is_(True))
        .order_by(ClusterTicket.rank)
    )
    return [ticket_from_row(r) for r in rows]


def _cluster_out(db: Session, cluster: Cluster) -> ClusterOut:
    return ClusterOut(
        id=cluster.id,
        cluster_index=cluster.cluster_index,
        name=cluster.name,
        description=cluster.description,
        ticket_count=cluster.ticket_count,
        representative_tickets=_representatives(db, cluster.id),
        faq=FaqOut.model_validate(cluster.faq) if cluster.faq else None,
        faq_error=cluster.faq_error,
        faq_status=_faq_status(cluster),
    )


def _get_cluster(db: Session, cluster_id: int) -> Cluster:
    cluster = db.scalar(select(Cluster).options(selectinload(Cluster.faq)).where(Cluster.id == cluster_id))
    if cluster is None:
        raise NotFoundError(f"Cluster {cluster_id} not found")
    return cluster


def list_clusters(db: Session) -> ClusterListOut:
    run = _latest_run(db)
    if run is None:
        return ClusterListOut(run=None, clusters=[])
    clusters = db.scalars(
        select(Cluster).options(selectinload(Cluster.faq)).where(Cluster.run_id == run.id).order_by(Cluster.cluster_index)
    )
    return ClusterListOut(run=RunOut.model_validate(run), clusters=[_cluster_out(db, c) for c in clusters])


def get_cluster_detail(db: Session, cluster_id: int) -> ClusterDetailOut:
    cluster = _get_cluster(db, cluster_id)
    base = _cluster_out(db, cluster)
    return ClusterDetailOut(**base.model_dump(), run=RunOut.model_validate(cluster.run))


def get_cluster_tickets(db: Session, cluster_id: int) -> List[Ticket]:
    _get_cluster(db, cluster_id)
    rows = db.scalars(
        select(TicketRow)
        .join(ClusterTicket, ClusterTicket.ticket_id == TicketRow.ticket_id)
        .where(ClusterTicket.cluster_id == cluster_id)
        .order_by(TicketRow.ticket_id)
    )
    return [ticket_from_row(r) for r in rows]


def get_cluster_faq(db: Session, cluster_id: int) -> FaqOut:
    cluster = _get_cluster(db, cluster_id)
    if cluster.faq is None:
        detail = cluster.faq_error or "no FAQ generated"
        raise NotFoundError(f"Cluster {cluster_id} has no FAQ ({detail})")
    return FaqOut.model_validate(cluster.faq)


def get_stats(db: Session) -> StatsOut:
    total = db.scalar(select(func.count()).select_from(TicketRow)) or 0
    resolved = db.scalar(select(func.count()).select_from(TicketRow).where(func.lower(TicketRow.status) == "resolved")) or 0
    listing = list_clusters(db)
    by_status = dict(db.execute(select(Faq.status, func.count()).group_by(Faq.status)).all())
    faqs = sum(by_status.values())
    for state in (GENERATION_FAILED, QUOTA_EXHAUSTED):
        count = sum(1 for c in listing.clusters if c.faq_status == state)
        if count:
            by_status[state] = count
    return StatsOut(
        total_tickets=total,
        resolved_tickets=resolved,
        clusters=len(listing.clusters),
        faqs=faqs,
        faqs_by_status=by_status,
        cluster_distribution=[{"cluster_id": c.id, "name": c.name, "ticket_count": c.ticket_count} for c in listing.clusters],
    )


def generate_cluster_faq(db: Session, cluster_id: int, llm: LLMProvider, cache_dir: str) -> ClusterOut:
    """Generate the FAQ for one cluster that has none. Clustering and embeddings are untouched."""
    cluster = _get_cluster(db, cluster_id)
    if cluster.faq is not None:
        raise FaqAlreadyExistsError(f"Cluster {cluster_id} already has an FAQ")
    tickets = _representatives(db, cluster.id)
    result = FaqGenerator(llm, cache_dir).generate_for_cluster(cluster.cluster_index, tickets, cluster.ticket_count)
    draft = result.faq
    if draft is None:
        cluster.faq_error = result.error or "FAQ was not generated"
    else:
        cluster.name, cluster.description, cluster.faq_error = draft.theme, draft.description, None
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
    db.refresh(cluster)
    return _cluster_out(db, cluster)


def regenerate_cluster_faq(db: Session, cluster_id: int, llm: LLMProvider, cache_dir: str) -> ClusterOut:
    """Replace a cluster's FAQ with a freshly generated one (always a new LLM call).

    The old FAQ is only overwritten once the new one is valid: if generation fails, nothing
    changes and FaqRegenerationError carries the user-facing reason. The row is updated in
    place, so the FAQ keeps its id; its status goes back to GENERATED for a new review.
    """
    cluster = _get_cluster(db, cluster_id)
    faq = cluster.faq
    if faq is None:
        raise NotFoundError(f"Cluster {cluster_id} has no FAQ to regenerate; generate one first")
    previous = FaqDraft(
        theme=faq.theme,
        description=faq.description,
        question=faq.question,
        answer=faq.answer,
        resolution_steps=faq.resolution_steps,
        source_ticket_ids=faq.source_ticket_ids,
        insufficient_information=faq.insufficient_information,
    )
    tickets = _representatives(db, cluster.id)
    result = FaqGenerator(llm, cache_dir).generate_for_cluster(
        cluster.cluster_index, tickets, cluster.ticket_count, previous=previous
    )
    draft = result.faq
    if draft is None:
        # keep the reason (first sentence); the "cluster was created" follow-up does not apply here
        reason = (result.error or "FAQ regeneration failed.").split(". ")[0].rstrip(".")
        raise FaqRegenerationError(f"{reason}. The existing FAQ was kept; try again later.")

    cluster.name, cluster.description, cluster.faq_error = draft.theme, draft.description, None
    faq.theme, faq.description = draft.theme, draft.description
    faq.question, faq.answer = draft.question, draft.answer
    faq.resolution_steps, faq.source_ticket_ids = draft.resolution_steps, draft.source_ticket_ids
    faq.insufficient_information = draft.insufficient_information
    faq.status = FaqStatus.GENERATED.value
    db.commit()
    db.refresh(cluster)
    return _cluster_out(db, cluster)


def generate_missing_faqs(db: Session, llm: LLMProvider, cache_dir: str) -> FaqBatchOut:
    """Generate the FAQ for every cluster of the latest run that has none, one at a time.

    Serves both the first "Generate FAQs" run and later retries. Stops calling the API as
    soon as it reports project quota exhaustion, marking the rest instead of hammering it.
    Clustering, embeddings and ticket processing are never re-run.
    """
    run = _latest_run(db)
    ids = []
    if run is not None:
        ids = list(
            db.scalars(
                select(Cluster.id)
                .outerjoin(Faq, Faq.cluster_id == Cluster.id)
                .where(Cluster.run_id == run.id, Faq.id.is_(None))
                .order_by(Cluster.cluster_index)
            )
        )

    outs: List[ClusterOut] = []
    quota_exhausted = False
    for cluster_id in ids:
        if quota_exhausted:
            outs.append(_mark_quota_exhausted(db, cluster_id))
            continue
        out = generate_cluster_faq(db, cluster_id, llm, cache_dir)
        quota_exhausted = out.faq_status == QUOTA_EXHAUSTED
        outs.append(out)

    generated = sum(1 for o in outs if o.faq is not None)
    return FaqBatchOut(
        attempted=len(outs),
        faqs_generated=generated,
        faqs_failed=len(outs) - generated,
        quota_exhausted=quota_exhausted,
        clusters=outs,
    )


def _mark_quota_exhausted(db: Session, cluster_id: int) -> ClusterOut:
    """Record the outcome for a cluster we deliberately did not call the API for."""
    cluster = _get_cluster(db, cluster_id)
    cluster.faq_error = MSG_QUOTA_EXHAUSTED
    db.commit()
    db.refresh(cluster)
    return _cluster_out(db, cluster)
