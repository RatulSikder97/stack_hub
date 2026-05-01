"""Detector contract — used by `run_ai_tells` and the calibration script."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field


class Flag(BaseModel):
    """A single AI-tells violation."""

    model_config = ConfigDict(extra="forbid")

    pattern: str
    snippet: str
    line_approx: int = Field(ge=0)


class DetectionResult(BaseModel):
    """Result of running a detector on a draft."""

    model_config = ConfigDict(extra="forbid")

    flags: list[Flag] = Field(default_factory=list)
    passed: bool

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> DetectionResult:
        flags_raw = data.get("flags", []) or []
        flags = [Flag.model_validate(f) for f in flags_raw if isinstance(f, dict)]
        passed = bool(data.get("passed")) and not flags
        return cls(flags=flags, passed=passed)


class Detector(ABC):
    """Run a single detection pass over a draft."""

    @abstractmethod
    def detect(self, draft_text: str) -> DetectionResult:
        """Inspect `draft_text` and return all AI-tell flags."""
