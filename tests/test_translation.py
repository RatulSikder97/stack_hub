"""Translator behavior with a stub provider."""

from __future__ import annotations

import json

import pytest

from pipeline.llm.base import GenerationRequest, LLMProvider
from pipeline.translation import TranslationParseError, Translator


class _StubProvider(LLMProvider):
    name = "stub"

    def __init__(self, response: str) -> None:
        self._api_key = "stub"
        self._model = "stub-model"
        self._response = response
        self.last_user_prompt: str | None = None

    def _generate(self, request: GenerationRequest) -> str:
        self.last_user_prompt = request.user_prompt
        return self._response


def test_translates_bengali_to_english() -> None:
    payload = json.dumps({"source_language": "bn", "translated_text": "Default decisions matter."})
    provider = _StubProvider(payload)
    result = Translator(provider).translate("ডিফল্ট সিদ্ধান্ত গুরুত্বপূর্ণ", target_language="en")
    assert result.source_language == "bn"
    assert result.translated_text == "Default decisions matter."
    assert result.target_language == "en"
    assert result.needed_translation is True


def test_no_translation_needed_when_already_target() -> None:
    payload = json.dumps({"source_language": "en", "translated_text": "Default decisions matter."})
    provider = _StubProvider(payload)
    result = Translator(provider).translate("Default decisions matter.", target_language="en")
    assert result.source_language == "en"
    assert result.needed_translation is False


def test_strips_code_fences_in_response() -> None:
    payload = "```json\n" + json.dumps({"source_language": "bn", "translated_text": "Hello"}) + "\n```"
    provider = _StubProvider(payload)
    result = Translator(provider).translate("হ্যালো")
    assert result.translated_text == "Hello"


def test_invalid_json_raises_parse_error() -> None:
    provider = _StubProvider("not json at all")
    with pytest.raises(TranslationParseError):
        Translator(provider).translate("test")


def test_empty_translation_raises_parse_error() -> None:
    payload = json.dumps({"source_language": "bn", "translated_text": ""})
    provider = _StubProvider(payload)
    with pytest.raises(TranslationParseError):
        Translator(provider).translate("test")


def test_empty_input_rejected() -> None:
    provider = _StubProvider("{}")
    with pytest.raises(ValueError, match="empty"):
        Translator(provider).translate("   ")


def test_provenance_block_format() -> None:
    payload = json.dumps({"source_language": "bn", "translated_text": "English version."})
    provider = _StubProvider(payload)
    result = Translator(provider).translate("বাংলা টেক্সট")
    block = result.render_provenance()
    assert "Original (bn)" in block
    assert "Translated to en" in block
    assert "বাংলা টেক্সট" in block
    assert "English version." in block
