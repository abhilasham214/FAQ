"""Minimal Gemini connectivity check, independent of the FAQ pipeline.

Usage (from backend/):
  python scripts/check_gemini.py             # one tiny request, no retries
  python scripts/check_gemini.py --attempts 5  # repeat it, 3 s apart

Reads GEMINI_API_KEY / GEMINI_MODEL / GEMINI_TIMEOUT_SECONDS from backend/.env. Never prints the key.
If this succeeds but FAQ generation fails, the FAQ request is the problem; if this
fails with 503 too, Gemini (or the API project) is unavailable.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.errors import LLMError  # noqa: E402
from app.llm.gemini import GeminiProvider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--attempts", type=int, default=1)
    args = parser.parse_args()

    settings = get_settings()
    try:
        provider = GeminiProvider(
            settings.gemini_api_key or "", settings.gemini_model, timeout_seconds=settings.gemini_timeout_seconds
        )
    except LLMError as exc:
        print(f"FAIL: {exc}")
        return 2

    print(f"model={provider.name}")
    failures = 0
    for i in range(1, args.attempts + 1):
        started = time.monotonic()
        try:
            reply = provider.ping()
            print(f"[{i}] OK in {time.monotonic() - started:.1f}s: {reply.strip()[:40]!r}")
        except LLMError as exc:
            failures += 1
            print(f"[{i}] FAIL in {time.monotonic() - started:.1f}s (status={exc.status}, transient={exc.transient}): {exc}")
        if i < args.attempts:
            time.sleep(3)
    print(f"{args.attempts - failures}/{args.attempts} succeeded")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
