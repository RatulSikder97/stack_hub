"""Abstract base for LLM providers.

Every concrete provider subclasses `LLMProvider` and implements `_generate`.
Callers depend on this interface — never on a specific SDK — so swapping
provider is a one-line config change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ProviderError(RuntimeError):
    """Generic provider failure (network, API, parsing)."""


class MissingAPIKeyError(ProviderError):
    """Provider was selected but its API key is missing."""


class RateLimitError(ProviderError):
    """Provider returned 429 / quota-exceeded.

    `retry_after_seconds` is best-effort parsed from the error payload —
    callers should display it to the user but not blindly trust it.
    """

    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class GenerationRequest:
    """Inputs for a single text generation call."""

    system_prompt: str
    user_prompt: str
    max_tokens: int = 1200
    temperature: float = 0.7


class LLMProvider(ABC):
    """Provider interface. Implementations must be stateless and idempotent."""

    name: str = "unknown"

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise MissingAPIKeyError(
                f"{type(self).__name__} requires a non-empty api_key. "
                f"Set the corresponding API key in your .env."
            )
        self._api_key = api_key
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 1200,
        temperature: float = 0.7,
    ) -> str:
        """Generate a single completion. Returns the assistant text."""
        request = GenerationRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            return self._generate(request).strip()
        except (ProviderError, KeyboardInterrupt):
            raise
        except Exception as exc:  # noqa: BLE001 — wrap SDK errors
            if _looks_like_rate_limit(exc):
                raise RateLimitError(
                    f"{type(self).__name__} rate-limited: {exc}",
                    retry_after_seconds=_parse_retry_seconds(str(exc)),
                ) from exc
            raise ProviderError(f"{type(self).__name__}.generate failed: {exc}") from exc

    @abstractmethod
    def _generate(self, request: GenerationRequest) -> str:
        """Subclass-only API. Translate `request` to the SDK call."""


# --- Rate-limit detection (cross-provider) --------------------------------

import re as _re


def _looks_like_rate_limit(exc: BaseException) -> bool:
    """Heuristic match across OpenAI / Gemini / Anthropic / Novita errors."""
    name = type(exc).__name__
    if name in {"RateLimitError", "ResourceExhausted", "ClientError"}:
        # google.genai surfaces 429 as ClientError with "RESOURCE_EXHAUSTED"
        msg = str(exc)
        if name == "ClientError" and "429" not in msg and "RESOURCE_EXHAUSTED" not in msg:
            return False
        return True
    msg = str(exc).lower()
    return (
        "429" in msg
        or "resource_exhausted" in msg
        or "rate limit" in msg
        or "rate_limit" in msg
        or "quota" in msg
        or "too many requests" in msg
    )


_RETRY_PATTERNS = (
    _re.compile(r"retry[_ -]?after[\":\s]+(\d+(?:\.\d+)?)", _re.IGNORECASE),
    _re.compile(r"retry in\s+(\d+(?:\.\d+)?)\s*s", _re.IGNORECASE),
    _re.compile(r"retryDelay['\":\s]+(\d+(?:\.\d+)?)s", _re.IGNORECASE),
)


def _parse_retry_seconds(message: str) -> float | None:
    for pattern in _RETRY_PATTERNS:
        match = pattern.search(message)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None
