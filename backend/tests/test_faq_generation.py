import json

import pytest
from pydantic import ValidationError

from app.clustering.kmeans import KMeansClusterer
from app.core.errors import InvalidLLMOutputError, LLMError
from app.llm.gemini import GeminiProvider
from app.llm.mock import MockLLMProvider
from app.prompts.faq_prompt import build_faq_prompt
from app.schemas.faq import FaqDraft
from app.schemas.ticket import Ticket
from app.services.clustering_service import cluster_tickets
from app.services.faq_generation import FaqGenerator, cache_key, parse_faq_json


def make_tickets(n=3, prefix="T"):
    return [
        Ticket(
            ticket_id=f"{prefix}{i}",
            title=f"Payment pending {i}",
            description="Payment stays pending",
            resolution=f"Reconciled transaction {i}",
            status="resolved",
        )
        for i in range(1, n + 1)
    ]


def valid_json(ids):
    return json.dumps(
        {
            "theme": "Payment pending",
            "description": "Payments stuck.",
            "question": "Why is my payment pending?",
            "answer": "Reconciled.",
            "resolution_steps": ["Reconcile"],
            "source_ticket_ids": ids,
        }
    )


class ScriptedProvider:
    """Returns / raises queued responses so tests control the LLM."""

    name = "scripted"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_json(self, prompt):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


# --- schema -------------------------------------------------------------

def test_faq_schema_rejects_missing_sources_and_blank_fields():
    with pytest.raises(ValidationError):
        FaqDraft(theme="t", description="d", question="q", answer="a", source_ticket_ids=[])
    with pytest.raises(ValidationError):
        FaqDraft(theme=" ", description="d", question="q", answer="a", source_ticket_ids=["T1"])


def test_parse_accepts_code_fenced_json():
    faq = parse_faq_json("```json\n" + valid_json(["T1"]) + "\n```", ["T1", "T2"])
    assert faq.source_ticket_ids == ["T1"]


def test_parse_rejects_invalid_json():
    with pytest.raises(InvalidLLMOutputError):
        parse_faq_json("not json at all", ["T1"])


def test_parse_rejects_invented_ticket_ids():
    with pytest.raises(InvalidLLMOutputError, match="not provided"):
        parse_faq_json(valid_json(["T1", "T999"]), ["T1", "T2"])


# --- prompt -------------------------------------------------------------

def test_prompt_contains_tickets_and_grounding_rules():
    prompt = build_faq_prompt(make_tickets(2), cluster_size=10)
    assert "[T1] Title:" in prompt and "Resolution: Reconciled transaction 2" in prompt
    assert "ONLY information present" in prompt and "insufficient_information" in prompt


# --- generator ----------------------------------------------------------

def test_generates_and_marks_result(tmp_path):
    gen = FaqGenerator(ScriptedProvider(valid_json(["T1", "T2"])), str(tmp_path))
    result = gen.generate_for_cluster(0, make_tickets(3), cluster_size=9)
    assert result.faq and result.error is None and not result.from_cache


def test_retries_once_on_invalid_output(tmp_path):
    provider = ScriptedProvider("garbage", valid_json(["T1"]))
    result = FaqGenerator(provider, str(tmp_path)).generate_for_cluster(0, make_tickets(), 3)
    assert result.faq is not None and provider.calls == 2


def test_gives_up_after_repeated_invalid_output(tmp_path):
    provider = ScriptedProvider("garbage", "still garbage")
    result = FaqGenerator(provider, str(tmp_path)).generate_for_cluster(0, make_tickets(), 3)
    assert result.faq is None and "validation" in result.error and provider.calls == 2


def test_llm_failure_is_captured_not_raised(tmp_path):
    provider = ScriptedProvider(LLMError("quota exceeded"))
    result = FaqGenerator(provider, str(tmp_path)).generate_for_cluster(0, make_tickets(), 3)
    assert result.faq is None and "quota" in result.error and provider.calls == 1


def test_cache_prevents_second_llm_call(tmp_path):
    provider = ScriptedProvider(valid_json(["T1"]))
    gen = FaqGenerator(provider, str(tmp_path))
    first = gen.generate_for_cluster(0, make_tickets(), 3)
    second = gen.generate_for_cluster(0, make_tickets(), 3)
    assert provider.calls == 1 and not first.from_cache and second.from_cache
    assert first.faq == second.faq


def test_cache_key_is_order_independent_and_content_sensitive():
    a = make_tickets(3)
    assert cache_key(a, "m") == cache_key(list(reversed(a)), "m")
    changed = make_tickets(3)
    changed[0].resolution = "Something else"
    assert cache_key(a, "m") != cache_key(changed, "m")
    assert cache_key(a, "m") != cache_key(a, "other-model")


def test_one_failing_cluster_does_not_stop_others(tmp_path, fake_embedder):
    tickets = []
    for phrase in ["payment pending gateway", "login password token", "refund bank amount"]:
        for i in range(8):
            tickets.append(
                Ticket(ticket_id=f"T{len(tickets) + 1}", title=phrase, description=f"{phrase} {i}",
                       resolution=phrase, status="resolved")
            )
    clustering = cluster_tickets(tickets, fake_embedder, KMeansClusterer())
    by_id = {t.ticket_id: t for t in tickets}
    # first cluster: provider failure; the rest: mock provider succeeds

    class FirstFails(MockLLMProvider):
        def generate_json(self, prompt):
            if self.calls == 0:
                self.calls += 1
                raise LLMError("boom")
            return super().generate_json(prompt)

    results = FaqGenerator(FirstFails(), str(tmp_path)).generate_all(clustering, by_id)
    assert len(results) == clustering.chosen_k
    assert results[0].error and all(r.faq for r in results[1:])


def test_mock_provider_output_is_valid_and_grounded(tmp_path):
    provider = MockLLMProvider()
    result = FaqGenerator(provider, str(tmp_path)).generate_for_cluster(0, make_tickets(4), 4)
    assert result.faq and set(result.faq.source_ticket_ids) == {"T1", "T2", "T3", "T4"}


def test_gemini_requires_api_key():
    with pytest.raises(LLMError):
        GeminiProvider("")
