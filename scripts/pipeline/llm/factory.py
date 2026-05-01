"""Factory + registry for LLM providers (Open/Closed extension point).

To add a new provider: implement `LLMProvider`, then `register_provider()`
the constructor here. `build_provider(settings)` will pick it up automatically
based on `settings.llm_provider`.
"""

from __future__ import annotations

from collections.abc import Callable

from pipeline.config import ProviderName, Settings
from pipeline.llm.anthropic_provider import AnthropicProvider
from pipeline.llm.base import LLMProvider, MissingAPIKeyError
from pipeline.llm.gemini_provider import GeminiProvider
from pipeline.llm.novita_provider import NovitaProvider
from pipeline.llm.openai_provider import OpenAIProvider

ProviderBuilder = Callable[[Settings], LLMProvider]


def _build_openai(settings: Settings) -> LLMProvider:
    return OpenAIProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url or None,
    )


def _build_gemini(settings: Settings) -> LLMProvider:
    return GeminiProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
    )


def _build_anthropic(settings: Settings) -> LLMProvider:
    return AnthropicProvider(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
    )


def _build_novita(settings: Settings) -> LLMProvider:
    return NovitaProvider(
        api_key=settings.novita_api_key,
        model=settings.novita_model,
        base_url=settings.novita_base_url,
    )


_REGISTRY: dict[ProviderName, ProviderBuilder] = {
    "openai": _build_openai,
    "gemini": _build_gemini,
    "anthropic": _build_anthropic,
    "novita": _build_novita,
}


def register_provider(name: ProviderName, builder: ProviderBuilder) -> None:
    """Register or override a provider builder. Useful for tests."""
    _REGISTRY[name] = builder


def available_providers() -> list[str]:
    return sorted(_REGISTRY.keys())


def build_provider(settings: Settings) -> LLMProvider:
    """Construct the provider configured in `settings`. Raises if key missing."""
    try:
        builder = _REGISTRY[settings.llm_provider]
    except KeyError as exc:
        raise ValueError(
            f"Unknown provider '{settings.llm_provider}'. "
            f"Available: {available_providers()}"
        ) from exc
    return builder(settings)


def has_active_provider(settings: Settings) -> bool:
    """True iff the configured provider can be constructed (key present)."""
    try:
        build_provider(settings)
    except MissingAPIKeyError:
        return False
    return True
