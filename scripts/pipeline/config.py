"""Typed settings for the pipeline, loaded from `.env` and process environment.

Uses `pydantic-settings` so misconfiguration fails loudly at startup instead of
deep inside an LLM call. Settings are immutable — callers cannot mutate them.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from pipeline.paths import CONFIG_PATH, ENV_PATH

ProviderName = Literal["openai", "gemini", "anthropic", "novita"]


class Settings(BaseSettings):
    """All runtime configuration in one place."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    # Provider selection.
    llm_provider: ProviderName = "openai"

    # Per-provider config.
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1"
    openai_base_url: str = ""

    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-pro"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-7"

    novita_api_key: str = ""
    novita_model: str = "meta-llama/llama-3.3-70b-instruct"
    novita_base_url: str = "https://api.novita.ai/v3/openai"

    # LLM tuning.
    llm_max_tokens_draft: int = Field(default=4000, ge=256, le=16000)
    llm_max_tokens_detector: int = Field(default=1200, ge=256, le=8000)
    llm_max_tokens_voice: int = Field(default=2000, ge=256, le=8000)
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Project metadata (loaded from data/config.json, not env).
    brand_name: str = "Stack Hub"
    cadence_days: int = Field(default=7, ge=1, le=90)

    @classmethod
    def load(cls) -> Settings:
        """Construct settings, layering `data/config.json` over env defaults."""
        instance = cls()  # type: ignore[call-arg]
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            overrides: dict[str, object] = {}
            if "brand_name" in data:
                overrides["brand_name"] = data["brand_name"]
            if "cadence_days" in data:
                overrides["cadence_days"] = int(data["cadence_days"])
            if overrides:
                instance = instance.model_copy(update=overrides)
        return instance

    def has_active_provider_key(self) -> bool:
        """True iff the currently selected provider has an API key set."""
        keys = {
            "openai": self.openai_api_key,
            "gemini": self.gemini_api_key,
            "anthropic": self.anthropic_api_key,
            "novita": self.novita_api_key,
        }
        return bool(keys[self.llm_provider])

    def model_for(self, provider: ProviderName | None = None) -> str:
        provider = provider or self.llm_provider
        return {
            "openai": self.openai_model,
            "gemini": self.gemini_model,
            "anthropic": self.anthropic_model,
            "novita": self.novita_model,
        }[provider]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor — call from any module."""
    return Settings.load()


def reset_settings_cache() -> None:
    """Clear the cached singleton. Used by tests that mutate env."""
    get_settings.cache_clear()
