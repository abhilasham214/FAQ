from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    """Minimal provider contract: prompt in, JSON text out.

    Implementations must raise `LLMError` on any provider failure. The app never
    imports a vendor SDK outside its own provider module.
    """

    name: str

    def generate_json(self, prompt: str) -> str: ...
