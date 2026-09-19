from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_cache_dir, get_embedder, get_llm
from app.core.errors import LLMError
from app.database.base import Base
from app.database.session import get_db
from app.llm.mock import MockLLMProvider
from app.main import app
from app import models  # noqa: F401  (register tables)

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample_tickets.csv"
HEADER = "ticket_id,title,description,resolution,status\n"


@pytest.fixture
def client(tmp_path, fake_embedder):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_embedder] = lambda: fake_embedder
    app.dependency_overrides[get_llm] = lambda: MockLLMProvider()
    app.dependency_overrides[get_cache_dir] = lambda: str(tmp_path)
    yield TestClient(app)  # no `with`: skips lifespan, so the real DB is never touched
    app.dependency_overrides.clear()


def upload(client, content: bytes, name="t.csv"):
    return client.post("/api/tickets/upload", files={"file": (name, content, "text/csv")})


@pytest.fixture
def loaded(client):
    assert upload(client, SAMPLE.read_bytes()).status_code == 200
    return client


@pytest.fixture
def generated(loaded):
    """Clusters only: /generate no longer spends LLM quota."""
    resp = loaded.post("/api/clusters/generate")
    assert resp.status_code == 200
    return loaded


@pytest.fixture
def with_faqs(generated):
    assert generated.post("/api/clusters/faqs/generate").status_code == 200
    return generated


class CountingProvider(MockLLMProvider):
    """Mock provider that fails every call with a chosen error, counting attempts."""

    def __init__(self, error: LLMError):
        super().__init__()
        self._error = error

    def generate_json(self, prompt):
        self.calls += 1
        raise self._error


def transient_error():
    return LLMError("503 provider says: quota exceeded", status=503, transient=True, error_type="SERVICE_UNAVAILABLE")


def quota_error():
    return LLMError(
        "429 you exceeded your current quota", status=429, transient=False, error_type="QUOTA_EXHAUSTED"
    )


# --- upload -------------------------------------------------------------

def test_upload_counts_and_rejects_bad_rows(client):
    body = HEADER + "T1,a,b,c,resolved\nT2,,b,c,resolved\n"
    data = upload(client, body.encode()).json()
    assert data["tickets_added"] == 1 and data["rejected_rows"][0]["row"] == 2


def test_duplicate_file_upload_is_409(client):
    body = (HEADER + "T1,a,b,c,resolved\n").encode()
    assert upload(client, body).status_code == 200
    assert upload(client, body).status_code == 409


def test_overlapping_ticket_ids_are_skipped(client):
    upload(client, (HEADER + "T1,a,b,c,resolved\n").encode())
    data = upload(client, (HEADER + "T1,a,b,c,resolved\nT2,a,b,c,resolved\n").encode()).json()
    assert data["tickets_added"] == 1 and data["tickets_skipped_existing"] == 1


def test_malformed_and_empty_uploads(client):
    assert upload(client, b"ticket_id,title\nT1,a\n").status_code == 400
    assert upload(client, b"").status_code == 422


# --- generate -----------------------------------------------------------

def test_generate_without_tickets_is_422(client):
    assert client.post("/api/clusters/generate").status_code == 422


def test_generate_with_too_few_tickets_is_422(client):
    upload(client, (HEADER + "T1,a,b,c,resolved\nT2,a,b,c,resolved\n").encode())
    assert client.post("/api/clusters/generate").status_code == 422


def test_generate_returns_steps_and_counts(loaded):
    data = loaded.post("/api/clusters/generate").json()
    assert data["clusters"] == data["run"]["chosen_k"]
    assert [s["name"] for s in data["steps"]] == ["Loaded tickets", "Generated embeddings", "Identified clusters"]


def test_clustering_spends_no_llm_quota(loaded):
    spy = MockLLMProvider()
    app.dependency_overrides[get_llm] = lambda: spy
    data = loaded.post("/api/clusters/generate").json()
    assert spy.calls == 0  # the whole point: clustering must not touch the provider
    assert data["clusters"] >= 3
    clusters = loaded.get("/api/clusters").json()["clusters"]
    assert all(c["faq"] is None and c["faq_status"] is None and c["faq_error"] is None for c in clusters)


def test_clusters_are_usable_without_any_faq(generated):
    """A clustering run stands on its own when the LLM is unavailable."""
    data = generated.get("/api/clusters").json()
    assert sum(c["ticket_count"] for c in data["clusters"]) == data["run"]["total_tickets"]
    assert all(c["representative_tickets"] for c in data["clusters"])
    detail = generated.get(f"/api/clusters/{data['clusters'][0]['id']}").json()
    assert detail["run"]["k_results"]


def test_faq_generation_is_a_separate_explicit_step(generated):
    spy = MockLLMProvider()
    app.dependency_overrides[get_llm] = lambda: spy
    result = generated.post("/api/clusters/faqs/generate").json()
    assert result["attempted"] == result["faqs_generated"] >= 3 and result["faqs_failed"] == 0
    assert result["quota_exhausted"] is False and spy.calls == result["attempted"]
    assert all(c["faq_status"] == "GENERATED" for c in generated.get("/api/clusters").json()["clusters"])
    assert generated.post("/api/clusters/faqs/generate").json()["attempted"] == 0  # nothing left to do


# --- read endpoints -----------------------------------------------------

def test_list_clusters_counts_sum_to_total(with_faqs):
    data = with_faqs.get("/api/clusters").json()
    assert 3 <= len(data["clusters"]) <= 5
    assert sum(c["ticket_count"] for c in data["clusters"]) == data["run"]["total_tickets"]
    assert all(c["faq"]["status"] == "GENERATED" for c in data["clusters"])


def test_list_clusters_empty_before_generation(client):
    assert client.get("/api/clusters").json() == {"run": None, "clusters": []}


def test_cluster_detail_tickets_and_faq_are_consistent(with_faqs):
    cluster = with_faqs.get("/api/clusters").json()["clusters"][0]
    detail = with_faqs.get(f"/api/clusters/{cluster['id']}").json()
    tickets = with_faqs.get(f"/api/clusters/{cluster['id']}/tickets").json()
    faq = with_faqs.get(f"/api/clusters/{cluster['id']}/faq").json()
    assert detail["run"]["k_results"] and len(tickets) == cluster["ticket_count"]
    ids = {t["ticket_id"] for t in tickets}
    assert set(faq["source_ticket_ids"]) <= ids  # traceability


def test_unknown_cluster_is_404(generated):
    for suffix in ("", "/tickets", "/faq"):
        assert generated.get(f"/api/clusters/9999{suffix}").status_code == 404


def test_stats(with_faqs):
    stats = with_faqs.get("/api/stats").json()
    assert stats["total_tickets"] == stats["resolved_tickets"] == 20
    assert stats["faqs"] == stats["clusters"] and stats["faqs_by_status"] == {"GENERATED": stats["faqs"]}


# --- review workflow ----------------------------------------------------

def first_faq_id(client):
    return client.get("/api/clusters").json()["clusters"][0]["faq"]["id"]


def test_approve_and_reject(with_faqs):
    faq_id = first_faq_id(with_faqs)
    assert with_faqs.post(f"/api/faqs/{faq_id}/approve").json()["status"] == "APPROVED"
    assert with_faqs.post(f"/api/faqs/{faq_id}/reject").json()["status"] == "REJECTED"
    assert with_faqs.post("/api/faqs/9999/approve").status_code == 404


def test_editing_moves_faq_back_to_review(with_faqs):
    faq_id = first_faq_id(with_faqs)
    with_faqs.post(f"/api/faqs/{faq_id}/approve")
    resp = with_faqs.patch(f"/api/faqs/{faq_id}", json={"answer": "Edited answer", "resolution_steps": ["one", "two"]})
    body = resp.json()
    assert body["status"] == "REVIEW" and body["answer"] == "Edited answer"
    assert body["resolution_steps"] == ["one", "two"] and body["question"]  # untouched field kept


def test_patch_validation_and_404(with_faqs):
    faq_id = first_faq_id(with_faqs)
    assert with_faqs.patch(f"/api/faqs/{faq_id}", json={"question": ""}).status_code == 422
    assert with_faqs.patch("/api/faqs/9999", json={"answer": "x"}).status_code == 404


# --- resilience ---------------------------------------------------------

def test_llm_failure_does_not_fail_clustering(generated):
    down = CountingProvider(transient_error())
    app.dependency_overrides[get_llm] = lambda: down
    data = generated.post("/api/clusters/faqs/generate").json()
    assert data["faqs_generated"] == 0 and data["faqs_failed"] == data["attempted"]
    cluster = generated.get("/api/clusters").json()["clusters"][0]
    assert cluster["faq"] is None and cluster["faq_status"] == "GENERATION_FAILED"
    assert "temporarily unavailable" in cluster["faq_error"] and "quota exceeded" not in cluster["faq_error"]
    assert cluster["ticket_count"] > 0 and cluster["representative_tickets"]  # the cluster itself is intact
    assert generated.get(f"/api/clusters/{cluster['id']}/faq").status_code == 404
    stats = generated.get("/api/stats").json()
    assert stats["faqs"] == 0 and stats["faqs_by_status"]["GENERATION_FAILED"] == data["attempted"]


def _fail_then(client, error=None):
    app.dependency_overrides[get_llm] = lambda: CountingProvider(error or transient_error())
    client.post("/api/clusters/faqs/generate")
    return client.get("/api/clusters").json()["clusters"]


def test_failed_faq_can_be_retried_without_reclustering(generated):
    before = _fail_then(generated)
    run_id = generated.get("/api/clusters").json()["run"]["id"]
    app.dependency_overrides[get_llm] = lambda: MockLLMProvider()  # provider is back
    target = before[0]
    out = generated.post(f"/api/clusters/{target['id']}/faq/generate").json()
    assert out["faq_status"] == "GENERATED" and out["faq"] and out["faq_error"] is None
    assert out["ticket_count"] == target["ticket_count"]
    listing = generated.get("/api/clusters").json()
    assert listing["run"]["id"] == run_id  # same run: nothing was re-embedded or re-clustered
    assert [c["id"] for c in listing["clusters"]] == [c["id"] for c in before]
    assert generated.get(f"/api/clusters/{target['id']}/faq").status_code == 200


def test_retry_that_fails_again_keeps_the_cluster(generated):
    before = _fail_then(generated)
    out = generated.post(f"/api/clusters/{before[0]['id']}/faq/generate").json()
    assert out["faq"] is None and out["faq_status"] == "GENERATION_FAILED"
    assert out["ticket_count"] == before[0]["ticket_count"]


def test_retry_failed_retries_every_failed_cluster(generated):
    before = _fail_then(generated)
    app.dependency_overrides[get_llm] = lambda: MockLLMProvider()
    result = generated.post("/api/clusters/faqs/retry-failed").json()
    assert result["attempted"] == len(before) and result["faqs_generated"] == len(before)
    assert result["faqs_failed"] == 0
    assert generated.post("/api/clusters/faqs/retry-failed").json()["attempted"] == 0


def test_retry_refuses_to_overwrite_an_existing_faq(with_faqs):
    cluster = with_faqs.get("/api/clusters").json()["clusters"][0]
    assert with_faqs.post(f"/api/clusters/{cluster['id']}/faq/generate").status_code == 409
    assert with_faqs.post("/api/clusters/9999/faq/generate").status_code == 404


# --- quota exhaustion ---------------------------------------------------

def test_quota_exhaustion_stops_calling_the_api_for_remaining_clusters(generated):
    down = CountingProvider(quota_error())
    app.dependency_overrides[get_llm] = lambda: down
    result = generated.post("/api/clusters/faqs/generate").json()
    assert down.calls == 1  # one call proves the quota is gone; the rest are marked, not attempted
    assert result["quota_exhausted"] is True and result["faqs_generated"] == 0
    assert result["faqs_failed"] == result["attempted"] >= 3
    clusters = generated.get("/api/clusters").json()["clusters"]
    assert all(c["faq_status"] == "QUOTA_EXHAUSTED" for c in clusters)
    assert all("quota" in c["faq_error"] and "429" not in c["faq_error"] for c in clusters)


def test_quota_exhausted_clusters_survive_and_can_be_retried(generated):
    before = _fail_then(generated, quota_error())
    assert all(c["faq_status"] == "QUOTA_EXHAUSTED" and c["ticket_count"] > 0 for c in before)
    stats = generated.get("/api/stats").json()
    assert stats["faqs"] == 0 and stats["faqs_by_status"]["QUOTA_EXHAUSTED"] == len(before)

    app.dependency_overrides[get_llm] = lambda: MockLLMProvider()  # quota reset
    result = generated.post("/api/clusters/faqs/retry-failed").json()
    assert result["faqs_generated"] == len(before) and result["quota_exhausted"] is False


def test_regenerate_replaces_previous_run(with_faqs):
    with_faqs.post("/api/clusters/generate")
    clusters = with_faqs.get("/api/clusters").json()["clusters"]
    assert all(c["faq"] is None for c in clusters)  # a fresh clustering run starts without FAQs
    with_faqs.post("/api/clusters/faqs/generate")
    assert with_faqs.get("/api/stats").json()["faqs"] == len(clusters)
