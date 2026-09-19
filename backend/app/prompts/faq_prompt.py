"""The prompt sent to the LLM for one cluster's FAQ.

Editing the prompt? Bump PROMPT_VERSION: it is part of the LLM cache key, so otherwise old
cached FAQs keep being returned and the change appears to do nothing.
"""
from __future__ import annotations

from typing import List, Optional

from app.schemas.faq import FaqDraft
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

"""

# Added only when regenerating, so the model does not simply return the same FAQ again.
_PREVIOUS = """PREVIOUS VERSION (a reviewer asked for a new one)
{previous}
Write a fresh version of this FAQ: improve clarity, completeness and wording rather than copying it.
The grounding rules above still apply; do not keep anything from the previous version that the tickets do not support.

"""


def build_faq_prompt(tickets: List[Ticket], cluster_size: int, previous: Optional[FaqDraft] = None) -> str:
    blocks = [
        f"[{t.ticket_id}] Title: {t.title}\nDescription: {t.description}\nResolution: {t.resolution}"
        for t in tickets
    ]
    header = _INSTRUCTIONS.format(cluster_size=cluster_size, shown=len(tickets))
    if previous is not None:
        header += _PREVIOUS.format(previous=previous.model_dump_json(indent=2))
    return header + "TICKETS\n" + "\n\n".join(blocks) + "\n"
