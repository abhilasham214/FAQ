"""Phase 1 demo: CSV -> embeddings -> K-Means (K=3,4,5) -> silhouette -> clusters.

Usage (from repo root): python backend/scripts/run_pipeline.py data/sample_tickets.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clustering.kmeans import KMeansClusterer  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.errors import FaqBuilderError  # noqa: E402
from app.embeddings.cache import CachedEmbedder  # noqa: E402
from app.embeddings.sentence_transformer import SentenceTransformerEmbedder  # noqa: E402
from app.services.clustering_service import cluster_tickets  # noqa: E402
from app.services.ingestion import parse_tickets_csv  # noqa: E402


def main() -> int:
    csv_path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/sample_tickets.csv")
    settings = get_settings()
    try:
        ingestion = parse_tickets_csv(csv_path.read_bytes())
        print(f"Loaded {len(ingestion.tickets)} tickets ({len(ingestion.errors)} rows rejected)")
        embedder = CachedEmbedder(SentenceTransformerEmbedder(settings.embedding_model), settings.cache_dir)
        result = cluster_tickets(ingestion.tickets, embedder, KMeansClusterer())
    except (FaqBuilderError, OSError) as exc:
        print(f"Error: {exc}")
        return 1

    by_id = {t.ticket_id: t for t in ingestion.tickets}
    print("\nSilhouette scores:")
    for r in result.k_results:
        marker = "  <-- selected" if r.k == result.chosen_k else ""
        print(f"  K={r.k}: {r.silhouette:.4f}{marker}")

    for cluster in result.clusters:
        print(f"\nCluster {cluster.cluster_id}  ({cluster.size} tickets)")
        for tid in cluster.representative_ticket_ids:
            print(f"  {tid}: {by_id[tid].title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
