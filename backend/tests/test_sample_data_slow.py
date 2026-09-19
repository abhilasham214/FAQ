from pathlib import Path

import pytest

from app.clustering.kmeans import KMeansClusterer
from app.embeddings.sentence_transformer import SentenceTransformerEmbedder
from app.services.clustering_service import cluster_tickets
from app.services.ingestion import parse_tickets_csv

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample_tickets.csv"


def test_sample_csv_parses_cleanly():
    result = parse_tickets_csv(SAMPLE.read_bytes())
    assert len(result.tickets) == 20
    assert result.errors == []


@pytest.mark.slow
def test_real_model_clusters_sample_data():
    tickets = parse_tickets_csv(SAMPLE.read_bytes()).tickets
    result = cluster_tickets(tickets, SentenceTransformerEmbedder(), KMeansClusterer())
    assert result.chosen_k in (3, 4, 5)
    assert sum(c.size for c in result.clusters) == len(tickets)
