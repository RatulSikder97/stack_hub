"""AI-tells detector implementations."""

from pipeline.detectors.base import DetectionResult, Detector, Flag
from pipeline.detectors.llm_judge import LLMJudgeDetector
from pipeline.detectors.local_kill_list import LocalKillListDetector

__all__ = [
    "DetectionResult",
    "Detector",
    "Flag",
    "LLMJudgeDetector",
    "LocalKillListDetector",
]
