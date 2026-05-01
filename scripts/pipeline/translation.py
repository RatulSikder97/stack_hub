"""Translate raw text into the brand's working language via any LLMProvider.

The translator returns both the rendered text and the detected source
language so callers can preserve provenance (e.g. keep the original Bengali
inside the brief alongside the English working version).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from pipeline.llm.base import LLMProvider
from pipeline.llm.text_utils import strip_code_fences


class TranslationParseError(RuntimeError):
    """Raised when the LLM returns a non-JSON response we cannot parse."""

    def __init__(self, raw_response: str) -> None:
        super().__init__(
            f"Translator returned non-JSON response (truncated):\n{raw_response[:600]}"
        )
        self.raw_response = raw_response


@dataclass(frozen=True)
class TranslationResult:
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    needed_translation: bool

    def render_provenance(self) -> str:
        """Markdown block suitable for embedding in a brief."""
        if not self.needed_translation:
            return f"_Source language: {self.source_language} (no translation needed)._\n"
        return (
            f"**Original ({self.source_language}):**\n\n"
            f"> {self.original_text}\n\n"
            f"**Translated to {self.target_language}:**\n\n"
            f"> {self.translated_text}\n"
        )


_SYSTEM_PROMPT = (
    "You are a precise translator. Detect the source language and translate "
    "the user's text into the requested target language. Preserve technical "
    "terms, names, and quoted material. Do not add commentary. "
    'Return ONLY valid JSON of this shape: '
    '{"source_language": "<ISO 639-1 code>", "translated_text": "<translation>"}. '
    "If the text is already in the target language, return source_language equal "
    "to the target and translated_text equal to the original."
)


class Translator:
    """Single-call translator over an `LLMProvider`."""

    def __init__(self, provider: LLMProvider, max_tokens: int = 4000) -> None:
        self._provider = provider
        self._max_tokens = max_tokens

    def translate(
        self,
        text: str,
        *,
        target_language: str = "en",
    ) -> TranslationResult:
        if not text or not text.strip():
            raise ValueError("Cannot translate empty text")

        user_prompt = (
            f"Target language: {target_language}\n\n"
            f"Text to translate:\n{text}"
        )
        raw = self._provider.generate(
            _SYSTEM_PROMPT,
            user_prompt,
            max_tokens=self._max_tokens,
            temperature=0.0,
        )
        cleaned = strip_code_fences(raw)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise TranslationParseError(raw) from exc

        if not isinstance(payload, dict):
            raise TranslationParseError(raw)

        source_language = str(payload.get("source_language", "")).strip().lower() or "unknown"
        translated_text = str(payload.get("translated_text", "")).strip()
        if not translated_text:
            raise TranslationParseError(raw)

        needed = source_language not in {target_language.lower(), "en", ""} or (
            translated_text.strip() != text.strip()
        )

        return TranslationResult(
            original_text=text.strip(),
            translated_text=translated_text,
            source_language=source_language,
            target_language=target_language.lower(),
            needed_translation=needed,
        )
