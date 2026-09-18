from __future__ import annotations

import json
import re


class MockLLMProvider:
    """Offline provider for development and tests.

    Builds a grounded-looking FAQ from the ticket blocks in the prompt (ids are
    read from "[T001]" markers) without calling any API.
    """

    name = "mock"

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(self, prompt: str) -> str:
        self.calls += 1
        ids = re.findall(r"^\[([^\]]+)\] Title: (.*)$", prompt, flags=re.MULTILINE)
        first_title = ids[0][1] if ids else "Unknown issue"
        resolutions = re.findall(r"^Resolution: (.*)$", prompt, flags=re.MULTILINE)
        return json.dumps(
            {
                "theme": f"Mock theme: {first_title}",
                "description": f"Mock summary of {len(ids)} related tickets.",
                "question": f"{first_title}: what should I do?",
                "answer": resolutions[0] if resolutions else "Insufficient information.",
                "resolution_steps": resolutions[:3],
                "source_ticket_ids": [tid for tid, _ in ids],
                "insufficient_information": not resolutions,
            }
        )
