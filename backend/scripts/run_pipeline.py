"""Demo: CSV -> embeddings -> K-Means (K=3,4,5) -> silhouette -> clusters -> (optional) FAQs.

Usage (from repo root):
  python backend/scripts/run_pipeline.py data/sample_tickets.csv              # clustering only
  python backend/scripts/run_pipeline.py data/sample_tickets.csv --llm mock   # + offline FAQs
  python backend/scripts/run_pipeline.py data/sample_tickets.csv --llm gemini # + Gemini FAQs
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clustering.kmeans import KMeansClusterer  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.errors import FaqBuilderError  # noqa: E402
from app.embeddings.cache import CachedEmbedder  # noqa: E402
from app.embeddings.sentence_transformer import SentenceTransformerEmbedder  # noqa: E402
from app.llm.gemini import GeminiProvider  # noqa: E402
from app.llm.mock import MockLLMProvider  # noqa: E402
from app.services.clustering_service import cluster_tickets  # noqa: E402
from app.services.faq_generation import FaqGenerator  # noqa: E402
from app.services.ingestion import parse_tickets_csv  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", nargs="?", default="data/sample_tickets.csv")
    parser.add_argument("--llm", choices=["mock", "gemini"], help="also generate one FAQ per cluster")
    args = parser.parse_args()
    csv_path = Path(args.csv_path)
    settings = get_settings()
    try:
        ingestion = parse_tickets_csv(csv_path.read_bytes())
        print(f"Loaded {len(ingestion.tickets)} tickets ({len(ingestion.errors)} rows rejected)")
        embedder = CachedEmbedder(SentenceTransformerEmbedder(settings.embedding_model), settings.cache_dir)
        result = cluster_tickets(ingestion.tickets, embedder, KMeansClusterer())
        faq_results = []
        if args.llm:
            provider = (
                MockLLMProvider()
                if args.llm == "mock"
                else GeminiProvider(settings.gemini_api_key or "", settings.gemini_model)
            )
            generator = FaqGenerator(provider, settings.cache_dir)
            faq_results = generator.generate_all(result, {t.ticket_id: t for t in ingestion.tickets})
    except (FaqBuilderError, OSError) as exc:
        print(f"Error: {exc}")
        return 1
    faq_by_cluster = {r.cluster_id: r for r in faq_results}

    by_id = {t.ticket_id: t for t in ingestion.tickets}
    print("\nSilhouette scores:")
    for r in result.k_results:
        marker = "  <-- selected" if r.k == result.chosen_k else ""
        print(f"  K={r.k}: {r.silhouette:.4f}{marker}")

    for cluster in result.clusters:
        print(f"\nCluster {cluster.cluster_id}  ({cluster.size} tickets)")
        for tid in cluster.representative_ticket_ids:
            print(f"  {tid}: {by_id[tid].title}")
        faq = faq_by_cluster.get(cluster.cluster_id)
        if faq and faq.faq:
            d = faq.faq
            print(f"  FAQ [{d.theme}]{' (cached)' if faq.from_cache else ''}")
            print(f"    Q: {d.question}")
            print(f"    A: {d.answer}")
            for step in d.resolution_steps:
                print(f"      - {step}")
            print(f"    Sources: {', '.join(d.source_ticket_ids)}")
        elif faq:
            print(f"  FAQ generation failed: {faq.error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
