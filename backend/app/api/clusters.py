from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_cache_dir, get_clusterer, get_embedder, get_llm
from app.database.session import get_db
from app.schemas.api import ClusterDetailOut, ClusterListOut, FaqOut, GenerateOut, RunOut
from app.schemas.ticket import Ticket
from app.services import cluster_service
from app.services.pipeline_service import generate_knowledge_base

router = APIRouter(prefix="/api/clusters", tags=["clusters"])


# Declared before "/{cluster_id}" so "generate" is never parsed as an id.
@router.post("/generate", response_model=GenerateOut)
def generate_clusters(
    db: Session = Depends(get_db),
    embedder=Depends(get_embedder),
    clusterer=Depends(get_clusterer),
    llm=Depends(get_llm),
    cache_dir: str = Depends(get_cache_dir),
) -> GenerateOut:
    run, faq_results, steps = generate_knowledge_base(db, embedder, clusterer, llm, cache_dir)
    failed = sum(1 for r in faq_results if r.faq is None)
    return GenerateOut(
        run=RunOut.model_validate(run),
        clusters=len(faq_results),
        faqs_generated=len(faq_results) - failed,
        faqs_failed=failed,
        steps=steps,
    )


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
