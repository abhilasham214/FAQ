import pytest
from sqlalchemy.exc import OperationalError

from app.api.deps import get_embedder
from app.core.errors import EmbeddingError
from app.database.session import get_db
from app.embeddings.sentence_transformer import SentenceTransformerEmbedder
from app.main import app

from tests.test_api import HEADER, client, loaded, upload  # noqa: F401  (reuse fixtures)


def test_embedding_model_load_failure_raises_embedding_error():
    embedder = SentenceTransformerEmbedder("definitely/not-a-real-model-name")
    embedder._load = lambda: (_ for _ in ()).throw(EmbeddingError("cannot load"))
    with pytest.raises(EmbeddingError):
        embedder.embed(["text"])


def test_embedding_encode_failure_is_wrapped():
    class Broken:
        def encode(self, *args, **kwargs):
            raise RuntimeError("out of memory")

    embedder = SentenceTransformerEmbedder()
    embedder._model = Broken()
    with pytest.raises(EmbeddingError, match="out of memory"):
        embedder.embed(["text"])


def test_embedding_failure_returns_502_and_keeps_existing_data(loaded):
    class Failing:
        name = "failing"

        def embed(self, texts):
            raise EmbeddingError("model unavailable")

    app.dependency_overrides[get_embedder] = lambda: Failing()
    resp = loaded.post("/api/clusters/generate")
    assert resp.status_code == 502 and "model unavailable" in resp.json()["detail"]
    assert loaded.get("/api/stats").json()["total_tickets"] == 20  # uploaded tickets untouched


def test_database_failure_returns_503(client):
    def broken_db():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = broken_db
    resp = client.get("/api/stats")
    assert resp.status_code == 503 and "Database error" in resp.json()["detail"]
    assert "connection refused" not in resp.text  # internals are not leaked


def test_non_utf8_upload_is_400(client):
    assert upload(client, b"\xff\xfe\x00\x01").status_code == 400


def test_upload_with_only_invalid_rows_is_422(client):
    assert upload(client, (HEADER + ",,,,\n").encode()).status_code == 422
