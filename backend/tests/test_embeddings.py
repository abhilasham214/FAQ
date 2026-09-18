import numpy as np

from app.embeddings.cache import CachedEmbedder
from app.schemas.ticket import Ticket
from app.services.preprocessing import ticket_to_text


def test_ticket_to_text_combines_fields():
    t = Ticket(ticket_id="T1", title="Pay  failed.", description="Card declined", resolution="Retried", status="resolved")
    assert ticket_to_text(t) == "Pay failed. Card declined. Retried."


def test_embedding_shape_and_normalisation(fake_embedder):
    vecs = fake_embedder.embed(["payment pending", "login failed"])
    assert vecs.shape == (2, fake_embedder.dim)
    assert np.allclose(np.linalg.norm(vecs, axis=1), 1.0)


def test_cache_avoids_recomputation(fake_embedder, tmp_path):
    cached = CachedEmbedder(fake_embedder, str(tmp_path))
    first = cached.embed(["a b", "c d"])
    assert fake_embedder.calls == 1
    second = cached.embed(["a b", "c d"])
    assert fake_embedder.calls == 1  # served fully from disk
    assert np.allclose(first, second)


def test_cache_only_embeds_misses(fake_embedder, tmp_path):
    cached = CachedEmbedder(fake_embedder, str(tmp_path))
    cached.embed(["a b"])
    out = cached.embed(["a b", "new text"])
    assert fake_embedder.calls == 2
    assert out.shape[0] == 2
