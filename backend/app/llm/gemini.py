from __future__ import annotations

from app.core.errors import LLMError


class GeminiProvider:
    """Gemini via the google-genai SDK, requesting JSON output."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set")
        self.name = model
        self._api_key = api_key
        self._client = None  # created lazily

    def generate_json(self, prompt: str) -> str:
        try:
            from google import genai
            from google.genai import types

            if self._client is None:
                self._client = genai.Client(api_key=self._api_key)
            response = self._client.models.generate_content(
                model=self.name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            text = response.text
        except Exception as exc:  # SDK raises many vendor-specific types
            raise LLMError(f"Gemini request failed: {exc}") from exc
        if not text:
            raise LLMError("Gemini returned an empty response")
        return text
