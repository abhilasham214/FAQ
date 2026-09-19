from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_cache_dir, get_clusterer, get_embedder, get_llm
from app.database.session import get_db
from app.schemas.api import ClusterDetailOut, ClusterListOut, ClusterOut, FaqBatchOut, FaqOut, GenerateOut, RunOut
from app.schemas.ticket import Ticket
from app.services import cluster_service
from app.services.pipeline_service import build_clusters

router = APIRouter(prefix="/api/clusters", tags=["clusters"])


# Declared before "/{cluster_id}" so "generate" is never parsed as an id.
@router.post("/generate", response_model=GenerateOut)
def generate_clusters(
    db: Session = Depends(get_db),
    embedder=Depends(get_embedder),
    clusterer=Depends(get_clusterer),
) -> GenerateOut:
    """Cluster the uploaded tickets. Spends no LLM quota: FAQs are generated separately."""
    run, steps = build_clusters(db, embedder, clusterer)
    return GenerateOut(run=RunOut.model_validate(run), clusters=len(run.clusters), steps=steps)


# Also before "/{cluster_id}". FAQ-only: clusters and embeddings are never recomputed.
@router.post("/faqs/generate", response_model=FaqBatchOut)
def generate_faqs(
    db: Session = Depends(get_db), llm=Depends(get_llm), cache_dir: str = Depends(get_cache_dir)
) -> FaqBatchOut:
    return cluster_service.generate_missing_faqs(db, llm, cache_dir)


@router.post("/faqs/retry-failed", response_model=FaqBatchOut)
def retry_failed_faqs(
    db: Session = Depends(get_db), llm=Depends(get_llm), cache_dir: str = Depends(get_cache_dir)
) -> FaqBatchOut:
    """Same work as /faqs/generate, kept as the explicit name for retrying failures."""
    return cluster_service.generate_missing_faqs(db, llm, cache_dir)


@router.get("", response_model=ClusterListOut)
def list_clusters(db: Session = Depends(get_db)) -> ClusterListOut:
    return cluster_service.list_clusters(db)


@router.get("/{cluster_id}", response_model=ClusterDetailOut)
def get_cluster(cluster_id: int, db: Session = Depends(get_db)) -> ClusterDetailOut:
    return cluster_service.get_cluster_detail(db, cluster_id)


@router.get("/{cluster_id}/tickets", response_model=List[Ticket])
def get_cluster_tickets(cluster_id: int, db: Session = Depends(get_db)) -> List[Ticket]:
    return cluster_service.get_cluster_tickets(db, cluster_id)


@router.get("/{cluster_id}/faq", response_model=FaqOut)
def get_cluster_faq(cluster_id: int, db: Session = Depends(get_db)) -> FaqOut:
    return cluster_service.get_cluster_faq(db, cluster_id)


@router.post("/{cluster_id}/faq/generate", response_model=ClusterOut)
def generate_cluster_faq(
    cluster_id: int, db: Session = Depends(get_db), llm=Depends(get_llm), cache_dir: str = Depends(get_cache_dir)
) -> ClusterOut:
    return cluster_service.generate_cluster_faq(db, cluster_id, llm, cache_dir)


@router.post("/{cluster_id}/faq/regenerate", response_model=ClusterOut)
def regenerate_cluster_faq(
    cluster_id: int, db: Session = Depends(get_db), llm=Depends(get_llm), cache_dir: str = Depends(get_cache_dir)
) -> ClusterOut:
    """Replace the cluster's FAQ with a new one. On failure (502) the existing FAQ is kept."""
    return cluster_service.regenerate_cluster_faq(db, cluster_id, llm, cache_dir)
