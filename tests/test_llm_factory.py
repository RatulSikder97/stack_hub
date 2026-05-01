"""LLM factory + provider registration."""

from __future__ import annotations

import pytest

from pipeline.config import Settings
from pipeline.llm import MissingAPIKeyError, build_provider, register_provider
from pipeline.llm.anthropic_provider import AnthropicProvider
from pipeline.llm.base import GenerationRequest, LLMProvider
from pipeline.llm.factory import available_providers, has_active_provider
from pipeline.llm.gemini_provider import GeminiProvider
from pipeline.llm.novita_provider import NovitaProvider
from pipeline.llm.openai_provider import OpenAIProvider


def _settings(provider: str, **kwargs: object) -> Settings:
    base = {
        "llm_provider": provider,
        "openai_api_key": "",
        "gemini_api_key": "",
        "anthropic_api_key": "",
        "novita_api_key": "",
    }
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


def test_available_providers_lists_all_four() -> None:
    assert {"openai", "gemini", "anthropic", "novita"} <= set(available_providers())


def test_build_provider_openai() -> None:
    settings = _settings("openai", openai_api_key="sk-test")
    provider = build_provider(settings)
    assert isinstance(provider, OpenAIProvider)


def test_build_provider_gemini() -> None:
    settings = _settings("gemini", gemini_api_key="key")
    provider = build_provider(settings)
    assert isinstance(provider, GeminiProvider)


def test_build_provider_anthropic() -> None:
    settings = _settings("anthropic", anthropic_api_key="key")
    provider = build_provider(settings)
    assert isinstance(provider, AnthropicProvider)


def test_build_provider_novita() -> None:
    settings = _settings("novita", novita_api_key="key")
    provider = build_provider(settings)
    assert isinstance(provider, NovitaProvider)


def test_build_provider_raises_missing_key() -> None:
    settings = _settings("openai")
    with pytest.raises(MissingAPIKeyError):
        build_provider(settings)


def test_has_active_provider_false_without_key() -> None:
    assert has_active_provider(_settings("openai")) is False


def test_register_provider_allows_extension() -> None:
    class _StubProvider(LLMProvider):
        name = "stub"

        def __init__(self) -> None:  # type: ignore[no-untyped-def]
            self._api_key = "stub"
            self._model = "stub"

        def _generate(self, request: GenerationRequest) -> str:
            return "stub"

    register_provider("openai", lambda settings: _StubProvider())  # type: ignore[arg-type]
    settings = _settings("openai")  # no key needed for stub
    provider = build_provider(settings)
    assert isinstance(provider, _StubProvider)
    # Restore real openai builder so other tests are unaffected.
    register_provider(
        "openai",
        lambda settings: OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url or None,
        ),
    )
