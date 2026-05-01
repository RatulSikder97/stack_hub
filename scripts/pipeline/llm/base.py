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
            raise ProviderError(f"{type(self).__name__}.generate failed: {exc}") from exc

    @abstractmethod
    def _generate(self, request: GenerationRequest) -> str:
        """Subclass-only API. Translate `request` to the SDK call."""
