import logging

import httpx
import pytest

from app.core.errors import LLMError
from app.llm.gemini import GeminiProvider

KEY = "sk-secret-key-123"


class ApiError(Exception):
    """Stands in for google.genai.errors.APIError: carries the HTTP status as `.code`."""

    def __init__(self, code, message="boom"):
        super().__init__(f"{code} {message}")
        self.code = code


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeClient:
    """`models.generate_content` replays queued results; exceptions are raised."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = []
        self.models = self

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)


def make(*results, **kwargs):
    sleeps = []
    client = FakeClient(*results)
    provider = GeminiProvider(KEY, "gemini-3.8-flash", sleep=sleeps.append, client=client, **kwargs)
    return provider, client, sleeps


def test_success_needs_one_request():
    provider, client, sleeps = make('{"ok": 1}')
    assert provider.generate_json("hi") == '{"ok": 1}'
    assert provider.requests == 1 and provider.retries == 0 and sleeps == []
    assert client.calls[0]["model"] == "gemini-3.8-flash"


def test_request_has_no_deprecated_gemini_2_parameters():
    provider, client, _ = make("{}")
    provider.generate_json("hi")
    config = client.calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.temperature is None and config.top_p is None and config.top_k is None
    assert config.candidate_count is None and config.thinking_config is None


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_transient_status_is_retried_then_succeeds(status):
    provider, _, sleeps = make(ApiError(status), ApiError(status), "{}", max_retries=2)
    assert provider.generate_json("hi") == "{}"
    assert provider.requests == 3 and provider.retries == 2 and len(sleeps) == 2


def test_backoff_is_exponential_with_bounded_jitter():
    provider, _, sleeps = make(*[ApiError(503)] * 5, max_retries=4)
    with pytest.raises(LLMError):
        provider.generate_json("hi")
    for waited, base in zip(sleeps, [1, 2, 4, 8]):
        assert base <= waited <= base * 1.25


def test_gives_up_after_bounded_retries():
    provider, client, sleeps = make(*[ApiError(503)] * 10, max_retries=4)
    with pytest.raises(LLMError) as info:
        provider.generate_json("hi")
    assert provider.requests == 5 and provider.retries == 4 and len(sleeps) == 4  # never retries forever
    assert len(client.results) == 5
    assert info.value.status == 503 and info.value.transient is True


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_are_not_retried(status):
    provider, _, sleeps = make(ApiError(status))
    with pytest.raises(LLMError) as info:
        provider.generate_json("hi")
    assert provider.requests == 1 and sleeps == []
    assert info.value.status == status and info.value.transient is False


def test_network_timeout_is_retried():
    provider, _, _ = make(httpx.ReadTimeout("slow"), "{}")
    assert provider.generate_json("hi") == "{}" and provider.retries == 1


def test_failure_is_logged_without_secrets(caplog):
    provider, _, _ = make(ApiError(503, f"overloaded key={KEY}"), "{}", max_retries=1)
    with caplog.at_level(logging.WARNING, logger="app.llm.gemini"):
        provider.generate_json("PRIVATE TICKET TEXT")
    text = caplog.text
    assert "status=503" in text and "model=gemini-3.8-flash" in text and "attempt=1/2" in text
    assert "error_type=SERVICE_UNAVAILABLE" in text
    assert KEY not in text and "PRIVATE TICKET TEXT" not in text


def test_error_message_does_not_contain_api_key():
    provider, _, _ = make(ApiError(400, f"bad request key={KEY}"))
    with pytest.raises(LLMError) as info:
        provider.generate_json("hi")
    assert KEY not in str(info.value)


def test_ping_is_a_single_attempt_without_retries():
    provider, client, sleeps = make(ApiError(503))
    with pytest.raises(LLMError):
        provider.ping()
    assert provider.requests == 1 and sleeps == []
    assert "OK" in client.calls[0]["contents"]


def test_ping_returns_text():
    provider, _, _ = make("OK")
    assert provider.ping() == "OK"


# --- quota exhaustion is terminal ----------------------------------------
QUOTA_MESSAGE = (
    "RESOURCE_EXHAUSTED: You exceeded your current quota, please check your plan and billing details."
)


def test_default_retry_budget_is_one():
    provider, _, sleeps = make(*[ApiError(503)] * 5)
    with pytest.raises(LLMError):
        provider.generate_json("hi")
    assert provider.requests == 2 and provider.retries == 1 and len(sleeps) == 1


def test_quota_exhaustion_is_not_retried():
    provider, _, sleeps = make(*[ApiError(429, QUOTA_MESSAGE)] * 5, max_retries=4)
    with pytest.raises(LLMError) as info:
        provider.generate_json("hi")
    assert provider.requests == 1 and provider.retries == 0 and sleeps == []  # retrying only burns more quota
    assert info.value.error_type == "QUOTA_EXHAUSTED"
    assert info.value.status == 429 and info.value.transient is False


def test_plain_rate_limit_is_still_retried():
    provider, _, sleeps = make(ApiError(429, "Too many requests, slow down"), "{}", max_retries=2)
    assert provider.generate_json("hi") == "{}"
    assert provider.retries == 1 and len(sleeps) == 1


@pytest.mark.parametrize("message", [
    "You exceeded your current quota",
    "quota_metric: generate_requests_per_model_per_day",
    "Quota exceeded for quota metric, limit PerDay",
    "free_tier limit reached",
])
def test_quota_wording_variants_are_detected(message):
    provider, _, _ = make(ApiError(429, message), max_retries=4)
    with pytest.raises(LLMError) as info:
        provider.generate_json("hi")
    assert info.value.error_type == "QUOTA_EXHAUSTED" and provider.requests == 1


def test_quota_exhaustion_is_logged_with_error_type(caplog):
    provider, _, _ = make(ApiError(429, QUOTA_MESSAGE))
    with caplog.at_level(logging.WARNING, logger="app.llm.gemini"):
        with pytest.raises(LLMError):
            provider.generate_json("hi")
    assert "error_type=QUOTA_EXHAUSTED" in caplog.text and "status=429" in caplog.text
    assert "model=gemini-3.8-flash" in caplog.text and "attempt=1/2" in caplog.text


@pytest.mark.parametrize("status,expected", [
    (500, "SERVICE_UNAVAILABLE"), (502, "SERVICE_UNAVAILABLE"), (503, "SERVICE_UNAVAILABLE"),
    (504, "SERVICE_UNAVAILABLE"), (408, "SERVICE_UNAVAILABLE"), (403, "CLIENT_ERROR"),
])
def test_error_types(status, expected):
    provider, _, _ = make(ApiError(status), max_retries=0)
    with pytest.raises(LLMError) as info:
        provider.generate_json("hi")
    assert info.value.error_type == expected
