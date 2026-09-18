from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List

from pydantic import ValidationError

from app.core.errors import InvalidLLMOutputError, LLMError
from app.llm.base import LLMProvider
from app.prompts.faq_prompt import PROMPT_VERSION, build_faq_prompt
from app.schemas.clustering import ClusteringResult
from app.schemas.faq import ClusterFaqResult, FaqDraft
from app.schemas.ticket import Ticket

MAX_ATTEMPTS = 2  # one retry when the model returns invalid / ungrounded JSON


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

    def generate_for_cluster(self, cluster_id: int, tickets: List[Ticket], cluster_size: int) -> ClusterFaqResult:
        allowed_ids = [t.ticket_id for t in tickets]
        path = self._dir / f"{cache_key(tickets, self._provider.name)}.json"

        cached = self._read_cache(path, allowed_ids)
        if cached is not None:
            return ClusterFaqResult(cluster_id=cluster_id, faq=cached, from_cache=True)

        prompt = build_faq_prompt(tickets, cluster_size)
        last_error = "unknown error"
        for _ in range(MAX_ATTEMPTS):
            try:
                faq = parse_faq_json(self._provider.generate_json(prompt), allowed_ids)
            except InvalidLLMOutputError as exc:
                last_error = str(exc)  # retry: the model may produce valid output next time
                continue
            except LLMError as exc:
                return ClusterFaqResult(cluster_id=cluster_id, error=str(exc))  # provider down: don't retry
            path.write_text(faq.model_dump_json(), encoding="utf-8")
            return ClusterFaqResult(cluster_id=cluster_id, faq=faq)
        return ClusterFaqResult(cluster_id=cluster_id, error=last_error)

    def generate_all(
        self, clustering: ClusteringResult, tickets_by_id: Dict[str, Ticket]
    ) -> List[ClusterFaqResult]:
        """Run every cluster independently; a failed cluster yields an error result, not an exception."""
        results = []
        for cluster in clustering.clusters:
            tickets = [tickets_by_id[tid] for tid in cluster.representative_ticket_ids]
            try:
                results.append(self.generate_for_cluster(cluster.cluster_id, tickets, cluster.size))
            except Exception as exc:  # last-resort guard so one cluster can't crash the run
                results.append(ClusterFaqResult(cluster_id=cluster.cluster_id, error=f"Unexpected error: {exc}"))
        return results

    @staticmethod
    def _read_cache(path: Path, allowed_ids: List[str]):
        if not path.exists():
            return None
        try:
            return parse_faq_json(path.read_text(encoding="utf-8"), allowed_ids)
        except (OSError, InvalidLLMOutputError):
            return None  # unreadable / stale entry: regenerate
