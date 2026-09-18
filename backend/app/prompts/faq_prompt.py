from __future__ import annotations

from typing import List

from app.schemas.ticket import Ticket

# Bump when the prompt changes so cached responses are not reused across versions.
PROMPT_VERSION = "v1"

_INSTRUCTIONS = """You are writing an internal knowledge-base FAQ entry from resolved support tickets.
All tickets below belong to ONE cluster of similar issues ({cluster_size} tickets in total; {shown} are shown).

STRICT GROUNDING RULES
- Use ONLY information present in the tickets below. Do not add causes, steps, tools, settings or timings that they do not mention.
- Every resolution step must be supported by at least one ticket's resolution.
- If the tickets do not contain enough information to answer reliably, set "insufficient_information" to true and say plainly in "answer" what is missing. Do not guess.
- "source_ticket_ids" must list only ticket IDs shown below that you actually used.

Respond with a single JSON object with exactly these keys:
{{
  "theme": "short name for this group of issues (3-6 words)",
  "description": "1-2 sentences describing the recurring problem",
  "question": "the FAQ question a user would ask",
  "answer": "concise answer grounded in the resolutions",
  "resolution_steps": ["ordered steps, each supported by the tickets"],
  "source_ticket_ids": ["T001"],
  "insufficient_information": false
}}

TICKETS
"""


def build_faq_prompt(tickets: List[Ticket], cluster_size: int) -> str:
    blocks = [
        f"[{t.ticket_id}] Title: {t.title}\nDescription: {t.description}\nResolution: {t.resolution}"
        for t in tickets
    ]
    header = _INSTRUCTIONS.format(cluster_size=cluster_size, shown=len(tickets))
    return header + "\n\n".join(blocks) + "\n"
