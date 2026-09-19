from __future__ import annotations

import logging

from app.core.errors import LLMError
from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class FallbackLLMProvider:
    """Tries the primary provider and falls back to a secondary one when it fails.

    `name` is the primary's, so cache lookups still target the primary's results.
    `used_fallback` reports whether the latest call was served by the fallback, so
    callers can avoid caching those results under the primary's name.
    """

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self.name = primary.name
        self.used_fallback = False
        self._primary = primary
        self._fallback = fallback

    def generate_json(self, prompt: str) -> str:
        try:
            text = self._primary.generate_json(prompt)
        except LLMError as exc:
            logger.warning("%s unavailable (%s); falling back to %s", self._primary.name, exc, self._fallback.name)
            self.used_fallback = True
            return self._fallback.generate_json(prompt)
        self.used_fallback = False
        return text
