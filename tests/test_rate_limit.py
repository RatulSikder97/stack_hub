"""Cross-provider rate-limit detection."""

from __future__ import annotations

import pytest

from pipeline.llm.base import (
    GenerationRequest,
    LLMProvider,
    ProviderError,
    RateLimitError,
    _looks_like_rate_limit,
    _parse_retry_seconds,
)


class _FakeRateLimitException(Exception):
    """Stand-in for SDK exceptions like google.genai.errors.ClientError."""


class _ExplodingProvider(LLMProvider):
    name = "exploder"

    def __init__(self, *, exc: BaseException) -> None:
        self._api_key = "stub"
        self._model = "stub"
        self._exc = exc

    def _generate(self, request: GenerationRequest) -> str:
        raise self._exc


def test_looks_like_rate_limit_matches_429_in_message() -> None:
    assert _looks_like_rate_limit(RuntimeError("429 RESOURCE_EXHAUSTED foo"))


def test_looks_like_rate_limit_matches_quota() -> None:
    assert _looks_like_rate_limit(RuntimeError("Exceeded daily quota"))


def test_looks_like_rate_limit_ignores_unrelated_errors() -> None:
    assert not _looks_like_rate_limit(RuntimeError("Connection reset by peer"))


def test_parse_retry_seconds_from_gemini_payload() -> None:
    msg = "Please retry in 38.4s. retryDelay: 38s"
    assert _parse_retry_seconds(msg) == pytest.approx(38.4)


def test_parse_retry_seconds_from_retry_after_header_style() -> None:
    msg = '{"error": "rate", "retry_after": 60}'
    # retry_after pattern requires a colon/space — this matches `retry_after": 60`
    assert _parse_retry_seconds(msg) == 60.0


def test_parse_retry_seconds_returns_none_when_absent() -> None:
    assert _parse_retry_seconds("nothing about waiting") is None


def test_provider_wraps_429_into_rate_limit_error() -> None:
    exc = _FakeRateLimitException(
        "429 RESOURCE_EXHAUSTED. Please retry in 38s. retryDelay: 38s"
    )
    provider = _ExplodingProvider(exc=exc)
    with pytest.raises(RateLimitError) as info:
        provider.generate("sys", "user")
    assert info.value.retry_after_seconds == pytest.approx(38.0)


def test_provider_passes_unrelated_error_through_provider_error() -> None:
    exc = RuntimeError("Connection refused")
    provider = _ExplodingProvider(exc=exc)
    with pytest.raises(ProviderError) as info:
        provider.generate("sys", "user")
    assert not isinstance(info.value, RateLimitError)
