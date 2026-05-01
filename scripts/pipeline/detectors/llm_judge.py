"""LLM-as-judge detector.

Used when a provider key is configured. Falls back to surfacing the raw
response if the model returns invalid JSON so the caller can debug.
"""

from __future__ import annotations

import json

from pipeline import paths as _paths
from pipeline.detectors.base import DetectionResult, Detector
from pipeline.llm.base import LLMProvider
from pipeline.llm.text_utils import strip_code_fences
from pipeline.templating import render_string


class DetectorParseError(RuntimeError):
    """Raised when the LLM response is not valid JSON in the expected shape."""

    def __init__(self, raw_response: str) -> None:
        super().__init__(
            f"Detector returned non-JSON response (truncated):\n{raw_response[:600]}"
        )
        self.raw_response = raw_response


SYSTEM_PROMPT = (
    "You are an AI-tells detector. "
    "Return ONLY valid JSON of the exact shape: "
    '{"flags": [{"pattern": str, "snippet": str, "line_approx": int}], "passed": bool}. '
    "Output no prose, no markdown code fences."
)


class LLMJudgeDetector(Detector):
    """Calls an `LLMProvider` to evaluate the draft against the kill list."""

    def __init__(self, provider: LLMProvider, max_tokens: int = 1200) -> None:
        self._provider = provider
        self._max_tokens = max_tokens
        self._prompt_template = _paths.DETECTOR_PROMPT_PATH.read_text(encoding="utf-8")
        self._kill_list = _paths.KILL_LIST_PATH.read_text(encoding="utf-8")

    def detect(self, draft_text: str) -> DetectionResult:
        user_prompt = render_string(
            self._prompt_template,
            kill_list=self._kill_list,
            draft_text=draft_text,
        )
        raw = self._provider.generate(
            SYSTEM_PROMPT,
            user_prompt,
            max_tokens=self._max_tokens,
            temperature=0.0,
        )
        cleaned = strip_code_fences(raw)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise DetectorParseError(raw) from exc
        if not isinstance(payload, dict):
            raise DetectorParseError(raw)
        return DetectionResult.from_dict(payload)
