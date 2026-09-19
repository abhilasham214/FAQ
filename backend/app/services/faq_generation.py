from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import ValidationError

from app.core.errors import InvalidLLMOutputError, LLMError
from app.llm.base import LLMProvider
from app.prompts.faq_prompt import PROMPT_VERSION, build_faq_prompt
from app.schemas.clustering import ClusteringResult
from app.schemas.faq import ClusterFaqResult, FaqDraft
from app.schemas.ticket import Ticket

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2  # one retry when the model returns invalid / ungrounded JSON

# What users see. Provider details stay in the backend log.
MSG_TEMPORARILY_UNAVAILABLE = (
    "FAQ generation is temporarily unavailable. The cluster was created successfully and can be retried."
)
MSG_REQUEST_FAILED = (
    "FAQ generation failed because of a provider configuration or request problem. "
    "The cluster was created successfully; check the server logs, then retry."
)
MSG_INVALID_OUTPUT = (
    "The model did not return a usable FAQ. The cluster was created successfully and can be retried."
)
MSG_QUOTA_EXHAUSTED = (
    "FAQ generation stopped: the AI provider's quota for this project is exhausted. "
    "The cluster was created successfully; retry once the quota resets."
)

QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
GENERATION_FAILED = "GENERATION_FAILED"

# Ceiling on API calls for one cluster, so the JSON retry and the provider's transient
# retries cannot multiply into a burst. Counted via the provider's own request counter.
MAX_REQUESTS_PER_CLUSTER = 3


def cache_key(tickets: List[Ticket], model_name: str) -> str:
    """Deterministic hash of the exact content sent to the LLM (order-independent)."""
    payload = {
        "model": model_name,
        "prompt_version": PROMPT_VERSION,
        "tickets": sorted(
            ([t.ticket_id, t.title, t.description, t.resolution] for t in tickets),
            key=lambda row: row[0],
        ),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def parse_faq_json(raw: str, allowed_ids: List[str]) -> FaqDraft:
    """Parse LLM text into a FaqDraft and enforce grounding on the source IDs."""
    text = raw.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        faq = FaqDraft.model_validate_json(text)
    except ValidationError as exc:
        raise InvalidLLMOutputError(f"LLM output failed schema validation: {exc.error_count()} error(s)") from exc

    unknown = [tid for tid in faq.source_ticket_ids if tid not in allowed_ids]
    if unknown:
        raise InvalidLLMOutputError(f"LLM cited ticket IDs that were not provided: {unknown}")
    return faq


class FaqGenerator:
    """Generates one FAQ per cluster: one LLM call per cluster, never per ticket."""

    def __init__(self, provider: LLMProvider, cache_dir: str) -> None:
        self._provider = provider
        self._dir = Path(cache_dir) / "llm"
        self._dir.mkdir(parents=True, exist_ok=True)

    def generate_for_cluster(
        self,
        cluster_id: int,
        tickets: List[Ticket],
        cluster_size: int,
        previous: Optional[FaqDraft] = None,
    ) -> ClusterFaqResult:
        """Generate one cluster's FAQ.

        Passing `previous` means "regenerate": the cache is skipped (it would hand back the
        same FAQ) and the model is shown the old version so it writes a fresh one. The new
        result then replaces the cache entry.
        """
        allowed_ids = [t.ticket_id for t in tickets]
        path = self._dir / f"{cache_key(tickets, self._provider.name)}.json"

        if previous is None:
            cached = self._read_cache(path, allowed_ids)
            if cached is not None:
                return ClusterFaqResult(cluster_id=cluster_id, faq=cached, from_cache=True)

        prompt = build_faq_prompt(tickets, cluster_size, previous)
        last_error = "unknown error"
        spent_at_start = self._requests_made()
        for _ in range(MAX_ATTEMPTS):
            try:
                faq = parse_faq_json(self._provider.generate_json(prompt), allowed_ids)
            except InvalidLLMOutputError as exc:
                last_error = str(exc)  # retry: the model may produce valid output next time
                if self._requests_made() - spent_at_start >= MAX_REQUESTS_PER_CLUSTER:
                    break  # the provider's own retries already used this cluster's budget
                continue
            except LLMError as exc:
                logger.warning("FAQ generation failed for cluster %s: %s", cluster_id, exc)
                if exc.error_type == QUOTA_EXHAUSTED:
                    return ClusterFaqResult(
                        cluster_id=cluster_id, error=MSG_QUOTA_EXHAUSTED, error_type=QUOTA_EXHAUSTED
                    )
                message = MSG_TEMPORARILY_UNAVAILABLE if exc.transient else MSG_REQUEST_FAILED
                # the provider already exhausted its bounded retries; nothing more to try here
                return ClusterFaqResult(cluster_id=cluster_id, error=message, error_type=GENERATION_FAILED)
            if not getattr(self._provider, "used_fallback", False):  # never cache fallback output as the primary's
                path.write_text(faq.model_dump_json(), encoding="utf-8")
            return ClusterFaqResult(cluster_id=cluster_id, faq=faq)
        logger.warning("FAQ generation failed for cluster %s: %s", cluster_id, last_error)
        return ClusterFaqResult(cluster_id=cluster_id, error=MSG_INVALID_OUTPUT, error_type=GENERATION_FAILED)

    def _requests_made(self) -> int:
        """API calls the provider has made so far (0 for providers that don't count)."""
        return getattr(self._provider, "requests", 0)

    def generate_all(
        self, clustering: ClusteringResult, tickets_by_id: Dict[str, Ticket]
    ) -> List[ClusterFaqResult]:
        """Run every cluster in turn; a failed cluster yields an error result, not an exception.

        Sequential by design (one in-flight request), and stops calling the API entirely once
        it reports project quota exhaustion: the remaining clusters are marked, not retried.
        """
        results: List[ClusterFaqResult] = []
        quota_exhausted = False
        for cluster in clustering.clusters:
            if quota_exhausted:
                results.append(
                    ClusterFaqResult(
                        cluster_id=cluster.cluster_id, error=MSG_QUOTA_EXHAUSTED, error_type=QUOTA_EXHAUSTED
                    )
                )
                continue
            tickets = [tickets_by_id[tid] for tid in cluster.representative_ticket_ids]
            try:
                result = self.generate_for_cluster(cluster.cluster_id, tickets, cluster.size)
            except Exception:  # last-resort guard so one cluster can't crash the run
                logger.exception("Unexpected error generating FAQ for cluster %s", cluster.cluster_id)
                result = ClusterFaqResult(
                    cluster_id=cluster.cluster_id, error=MSG_REQUEST_FAILED, error_type=GENERATION_FAILED
                )
            if result.error_type == QUOTA_EXHAUSTED:
                quota_exhausted = True
                logger.warning("Quota exhausted; skipping API calls for the remaining clusters")
            results.append(result)
        return results

    @staticmethod
    def _read_cache(path: Path, allowed_ids: List[str]):
        if not path.exists():
            return None
        try:
            return parse_faq_json(path.read_text(encoding="utf-8"), allowed_ids)
        except (OSError, InvalidLLMOutputError):
            return None  # unreadable / stale entry: regenerate
