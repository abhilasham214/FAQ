from __future__ import annotations

import logging
import random
import re
import time
from typing import Any, Callable, Optional

from app.core.errors import LLMError

logger = logging.getLogger(__name__)

# Infrastructure hiccups worth retrying. 400/401/403/404 are request or setup problems: retrying can't fix them.
RETRYABLE_STATUSES = frozenset({408, 500, 502, 503, 504})
MAX_DELAY_SECONDS = 30.0
MIN_TIMEOUT_SECONDS = 10.0  # Google rejects request deadlines shorter than 10 s
MAX_LOGGED_ERROR_CHARS = 300

QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"

# A 429 is either short-term rate limiting (retry) or the project's quota being spent
# (terminal: retrying just burns more of it). Google separates the two only in the message.
QUOTA_MARKERS = (
    "exceeded your current quota",
    "check your plan and billing",
    "quota_metric",
    "perday",
    "per day",
    "daily limit",
    "free_tier",
)


class GeminiProvider:
    """Gemini via the google-genai SDK, requesting JSON output.

    Gemini 3.x rejects the old sampling parameters (temperature / top_p / top_k /
    candidate_count), so the request sets only the response type. Transient failures
    are retried with bounded exponential backoff and jitter.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout_seconds: float = 60.0,
        max_retries: int = 1,
        base_delay: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        client: Any = None,
    ) -> None:
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set")
        self.name = model
        self.requests = 0  # HTTP requests sent, including retries
        self.retries = 0
        self._api_key = api_key
        self._timeout_seconds = max(timeout_seconds, MIN_TIMEOUT_SECONDS)
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._sleep = sleep
        self._client = client  # created lazily

    def generate_json(self, prompt: str) -> str:
        return self._request(prompt, self._max_retries)

    def ping(self) -> str:
        """One minimal request, no retries: tells "Gemini/API unavailable" apart from "our request is the problem"."""
        return self._request("Return the word OK.", max_retries=0, json_output=False)

    # ------------------------------------------------------------------
    def _request(self, prompt: str, max_retries: int, json_output: bool = True) -> str:
        for attempt in range(1, max_retries + 2):
            started = time.monotonic()
            self.requests += 1
            try:
                text = self._call(prompt, json_output)
            except Exception as exc:  # SDK raises many vendor-specific types
                status, error_type, transient = _classify(exc)
                elapsed = time.monotonic() - started
                detail = self._sanitize(exc)
                logger.warning(
                    "Gemini request failed: model=%s status=%s error_type=%s attempt=%d/%d elapsed=%.1fs error=%s",
                    self.name, status if status is not None else "n/a", error_type,
                    attempt, max_retries + 1, elapsed, detail,
                )
                if transient and attempt <= max_retries:
                    self.retries += 1
                    self._sleep(_backoff(attempt, self._base_delay))
                    continue
                raise LLMError(
                    f"Gemini request failed: model={self.name} status={status} "
                    f"error_type={error_type} attempts={attempt}: {detail}",
                    status=status,
                    transient=transient,
                    error_type=error_type,
                ) from exc
            if not text:
                raise LLMError(
                    "Gemini returned an empty response", status=None, transient=True, error_type="EMPTY_RESPONSE"
                )
            return text
        raise AssertionError("unreachable")  # loop always returns or raises

    def _call(self, prompt: str, json_output: bool) -> Optional[str]:
        from google.genai import types

        config = types.GenerateContentConfig(response_mime_type="application/json") if json_output else None
        response = self._get_client().models.generate_content(model=self.name, contents=prompt, config=config)
        return response.text

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai
            from google.genai import types

            # HttpOptions.timeout is in milliseconds
            options = types.HttpOptions(timeout=int(self._timeout_seconds * 1000))
            self._client = genai.Client(api_key=self._api_key, http_options=options)
        return self._client

    def _sanitize(self, exc: Exception) -> str:
        """Single-line, length-capped error text with the API key removed."""
        text = re.sub(r"\s+", " ", str(exc)).replace(self._api_key, "***")
        return text[:MAX_LOGGED_ERROR_CHARS]


def _classify(exc: Exception) -> "tuple[Optional[int], str, bool]":
    """(HTTP status if any, error_type, is the failure worth retrying?)"""
    status = getattr(exc, "code", None)
    if isinstance(status, int):
        if status == 429:
            if _is_quota_exhausted(str(exc)):
                return status, QUOTA_EXHAUSTED, False  # terminal: more calls only dig the hole deeper
            return status, "RATE_LIMITED", True
        if status in RETRYABLE_STATUSES:
            return status, "SERVICE_UNAVAILABLE", True
        return status, "CLIENT_ERROR", False
    try:
        import httpx

        if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
            return None, "NETWORK", True  # timeout / connection reset: worth another try
    except ImportError:  # pragma: no cover
        pass
    return None, "UNKNOWN", False


def _is_quota_exhausted(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in QUOTA_MARKERS)


def _backoff(attempt: int, base_delay: float) -> float:
    """1s, 2s, 4s, 8s ... (times base_delay) plus up to 25% jitter, capped."""
    delay = min(base_delay * (2 ** (attempt - 1)), MAX_DELAY_SECONDS)
    return delay + random.uniform(0, delay * 0.25)
