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
    resp = loaded.post("/api/clusters/generate")
    assert resp.status_code == 200
    return loaded


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
    assert data["clusters"] == data["run"]["chosen_k"] and data["faqs_failed"] == 0
    assert [s["name"] for s in data["steps"]][0] == "Loaded tickets"


# --- read endpoints -----------------------------------------------------

def test_list_clusters_counts_sum_to_total(generated):
    data = generated.get("/api/clusters").json()
    assert 3 <= len(data["clusters"]) <= 5
    assert sum(c["ticket_count"] for c in data["clusters"]) == data["run"]["total_tickets"]
    assert all(c["faq"]["status"] == "GENERATED" for c in data["clusters"])


def test_list_clusters_empty_before_generation(client):
    assert client.get("/api/clusters").json() == {"run": None, "clusters": []}


def test_cluster_detail_tickets_and_faq_are_consistent(generated):
    cluster = generated.get("/api/clusters").json()["clusters"][0]
    detail = generated.get(f"/api/clusters/{cluster['id']}").json()
    tickets = generated.get(f"/api/clusters/{cluster['id']}/tickets").json()
    faq = generated.get(f"/api/clusters/{cluster['id']}/faq").json()
    assert detail["run"]["k_results"] and len(tickets) == cluster["ticket_count"]
    ids = {t["ticket_id"] for t in tickets}
    assert set(faq["source_ticket_ids"]) <= ids  # traceability


def test_unknown_cluster_is_404(generated):
    for suffix in ("", "/tickets", "/faq"):
        assert generated.get(f"/api/clusters/9999{suffix}").status_code == 404


def test_stats(generated):
    stats = generated.get("/api/stats").json()
    assert stats["total_tickets"] == stats["resolved_tickets"] == 153
    assert stats["faqs"] == stats["clusters"] and stats["faqs_by_status"] == {"GENERATED": stats["faqs"]}


# --- review workflow ----------------------------------------------------

def first_faq_id(client):
    return client.get("/api/clusters").json()["clusters"][0]["faq"]["id"]


def test_approve_and_reject(generated):
    faq_id = first_faq_id(generated)
    assert generated.post(f"/api/faqs/{faq_id}/approve").json()["status"] == "APPROVED"
    assert generated.post(f"/api/faqs/{faq_id}/reject").json()["status"] == "REJECTED"
    assert generated.post("/api/faqs/9999/approve").status_code == 404


def test_editing_moves_faq_back_to_review(generated):
    faq_id = first_faq_id(generated)
    generated.post(f"/api/faqs/{faq_id}/approve")
    resp = generated.patch(f"/api/faqs/{faq_id}", json={"answer": "Edited answer", "resolution_steps": ["one", "two"]})
    body = resp.json()
    assert body["status"] == "REVIEW" and body["answer"] == "Edited answer"
    assert body["resolution_steps"] == ["one", "two"] and body["question"]  # untouched field kept


def test_patch_validation_and_404(generated):
    faq_id = first_faq_id(generated)
    assert generated.patch(f"/api/faqs/{faq_id}", json={"question": ""}).status_code == 422
    assert generated.patch("/api/faqs/9999", json={"answer": "x"}).status_code == 404


# --- resilience ---------------------------------------------------------

def test_llm_failure_does_not_fail_generation(loaded):
    class AlwaysDown(MockLLMProvider):
        def generate_json(self, prompt):
            raise LLMError("quota exceeded")

    app.dependency_overrides[get_llm] = lambda: AlwaysDown()
    data = loaded.post("/api/clusters/generate").json()
    assert data["faqs_generated"] == 0 and data["faqs_failed"] == data["clusters"]
    cluster = loaded.get("/api/clusters").json()["clusters"][0]
    assert cluster["faq"] is None and "quota" in cluster["faq_error"]
    assert loaded.get(f"/api/clusters/{cluster['id']}/faq").status_code == 404


def test_regenerate_replaces_previous_run(generated):
    generated.post("/api/clusters/generate")
    assert generated.get("/api/stats").json()["faqs"] == len(generated.get("/api/clusters").json()["clusters"])
