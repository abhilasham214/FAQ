"""Tables for a clustering run: the run itself, its clusters, and cluster <-> ticket membership.

Only the latest run is kept: pipeline_service._replace_run deletes the old rows on every
re-cluster, including FAQs.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ClusterRun(Base):
    """One execution of the clustering pipeline (only the latest run is kept)."""

    __tablename__ = "cluster_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chosen_k: Mapped[int] = mapped_column(Integer)
    silhouette: Mapped[float] = mapped_column(Float)
    k_results: Mapped[list] = mapped_column(JSON)  # [{"k": 3, "silhouette": 0.17}, ...]
    total_tickets: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    clusters: Mapped[List["Cluster"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="Cluster.cluster_index"
    )


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("cluster_runs.id"))
    cluster_index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    ticket_count: Mapped[int] = mapped_column(Integer)
    faq_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    run: Mapped[ClusterRun] = relationship(back_populates="clusters")
    members: Mapped[List["ClusterTicket"]] = relationship(cascade="all, delete-orphan")
    faq: Mapped[Optional["Faq"]] = relationship(back_populates="cluster", cascade="all, delete-orphan", uselist=False)  # noqa: F821


class ClusterTicket(Base):
    __tablename__ = "cluster_tickets"

    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.ticket_id"), primary_key=True)
    is_representative: Mapped[bool] = mapped_column(Boolean, default=False)
    rank: Mapped[int] = mapped_column(Integer, default=0)  # closeness to centroid among representatives
