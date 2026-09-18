from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError
from app.models import Cluster, ClusterRun, ClusterTicket, Faq, TicketRow
from app.schemas.api import ClusterDetailOut, ClusterListOut, ClusterOut, FaqOut, RunOut, StatsOut
from app.schemas.ticket import Ticket
from app.services.ticket_service import ticket_from_row


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
    return StatsOut(
        total_tickets=total,
        resolved_tickets=resolved,
        clusters=len(listing.clusters),
        faqs=sum(by_status.values()),
        faqs_by_status=by_status,
        cluster_distribution=[{"cluster_id": c.id, "name": c.name, "ticket_count": c.ticket_count} for c in listing.clusters],
    )
