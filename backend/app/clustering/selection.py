"""Pick the winning K from the silhouette scores."""
from __future__ import annotations

from typing import Sequence

from app.schemas.clustering import KResult


def select_best(results: Sequence[KResult]) -> KResult:
    """Highest silhouette wins; ties go to the smaller K (simpler model)."""
    if not results:
        raise ValueError("No clustering results to select from")
    return max(results, key=lambda r: (r.silhouette, -r.k))
