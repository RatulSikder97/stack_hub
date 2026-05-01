#!/usr/bin/env python3
"""Sprint-grade calibration.

Generates 5 AI drafts via the configured provider, samples 5 corpus posts,
shuffles them, and asks the same provider (acting as judge) to score each
on AI-likelihood. Computes the rate at which the judge correctly identifies
AI vs. human. Gate <70% to pass.

Real human panel is more reliable. AI-as-judge for speed.

When no provider key is configured, the script switches to a local heuristic
mode that scores using the kill-list detector flag count. This still
provides a real signal — drafts hitting more AI-tells are flagged AI — but
is less accurate than a model judge.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

from pipeline import paths as _paths
from pipeline.config import get_settings
from pipeline.detectors import LocalKillListDetector
from pipeline.llm import LLMProvider, MissingAPIKeyError, build_provider
from pipeline.llm.base import ProviderError
from pipeline.llm.text_utils import strip_code_fences
from pipeline.logging_config import get_logger
from pipeline.paths import ensure_dirs

LOG = get_logger(__name__)

SAMPLE_SIZE = 5
GATE_THRESHOLD = 70.0


def _calibration_dir() -> "Path":  # noqa: F821 — forward type hint
    return _paths.DRAFTS_DIR / "calibration"


JUDGE_SYSTEM = (
    "You are a strict judge. For each post, return ONLY a JSON array of "
    "objects {\"id\": str, \"ai_likelihood\": int 0-10}. 10 = certainly AI; "
    "0 = certainly human. No prose, no markdown fences."
)


@dataclass(frozen=True)
class Sample:
    sample_id: str
    text: str
    is_ai: bool


def _list_corpus_posts() -> list[Path]:
    if not _paths.CORPUS_DIR.exists():
        return []
    return sorted(_paths.CORPUS_DIR.glob("**/*.md"))


def _generate_ai_samples(
    provider: LLMProvider | None, n: int, system_prompt: str
) -> list[str]:
    if provider is None:
        return [
            "# Mock AI draft\n\nIn a world where time is short, focus matters most. "
            "It's not just productivity, it's identity. Let's dive into the details — "
            "carefully, slowly, deliberately. The choice is yours.\n"
            for _ in range(n)
        ]
    user_prompt = (
        "Write a 250-300 word Substack post on a generic productivity topic. "
        "Use whichever style feels natural to you."
    )
    return [
        provider.generate(system_prompt, user_prompt, max_tokens=600, temperature=0.7)
        for _ in range(n)
    ]


def _build_judge_system_prompt() -> str:
    voice = (
        _paths.VOICE_MAP_PATH.read_text(encoding="utf-8")
        if _paths.VOICE_MAP_PATH.exists()
        else ""
    )
    promise = (
        _paths.BRAND_PROMISE_PATH.read_text(encoding="utf-8")
        if _paths.BRAND_PROMISE_PATH.exists()
        else ""
    )
    kills = (
        _paths.KILL_LIST_PATH.read_text(encoding="utf-8")
        if _paths.KILL_LIST_PATH.exists()
        else ""
    )
    return (
        f"{JUDGE_SYSTEM}\n\nReference voice and brand context:\n{promise}\n\n{voice}\n\n"
        f"AI-tell patterns to penalize:\n{kills}"
    )


def _build_samples(provider: LLMProvider | None, system_prompt: str) -> list[Sample]:
    corpus_posts = _list_corpus_posts()
    if not corpus_posts:
        raise RuntimeError("No corpus posts found — calibration requires a corpus.")

    human_picks = random.sample(corpus_posts, k=min(SAMPLE_SIZE, len(corpus_posts)))
    human_samples = [
        Sample(
            sample_id=f"human_{i}",
            text=path.read_text(encoding="utf-8"),
            is_ai=False,
        )
        for i, path in enumerate(human_picks, start=1)
    ]

    ai_texts = _generate_ai_samples(provider, SAMPLE_SIZE, system_prompt)
    ai_samples = [
        Sample(sample_id=f"ai_{i}", text=text, is_ai=True)
        for i, text in enumerate(ai_texts, start=1)
    ]

    return human_samples + ai_samples


def _persist_samples(samples: list[Sample]) -> None:
    cal_dir = _calibration_dir()
    cal_dir.mkdir(parents=True, exist_ok=True)
    for sample in samples:
        (cal_dir / f"{sample.sample_id}.md").write_text(sample.text, encoding="utf-8")


def _judge_with_provider(
    provider: LLMProvider, samples: list[Sample], system_prompt: str
) -> dict[str, int]:
    shuffled = list(samples)
    random.shuffle(shuffled)
    payload = "\n\n".join(
        f"### id={sample.sample_id}\n{sample.text.strip()}" for sample in shuffled
    )
    raw = provider.generate(system_prompt, payload, max_tokens=1200, temperature=0.0)
    cleaned = strip_code_fences(raw)
    try:
        scores = json.loads(cleaned)
    except json.JSONDecodeError:
        LOG.warning("Judge returned non-JSON, falling back to local heuristic.")
        return _judge_locally(samples)
    if not isinstance(scores, list):
        return _judge_locally(samples)
    return {
        item["id"]: int(item.get("ai_likelihood", 0))
        for item in scores
        if isinstance(item, dict) and "id" in item
    }


def _judge_locally(samples: list[Sample]) -> dict[str, int]:
    detector = LocalKillListDetector()
    return {s.sample_id: min(10, len(detector.detect(s.text).flags) * 3) for s in samples}


def _detection_rate(samples: list[Sample], scores: dict[str, int]) -> float:
    if not samples:
        return 0.0
    correct = 0
    for sample in samples:
        score = scores.get(sample.sample_id)
        if score is None:
            continue
        predicted_ai = score >= 6
        if predicted_ai == sample.is_ai:
            correct += 1
    return 100.0 * correct / len(samples)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run sprint-grade voice calibration"
    )
    parser.add_argument(
        "--seed", type=int, default=None, help="Random seed for reproducibility"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.seed is not None:
        random.seed(args.seed)
    ensure_dirs()

    settings = get_settings()
    provider: LLMProvider | None
    try:
        provider = build_provider(settings) if settings.has_active_provider_key() else None
    except MissingAPIKeyError:
        provider = None

    judge_system = _build_judge_system_prompt()

    if provider is None:
        LOG.info("Calibrating in local mode (no provider key).")
    else:
        LOG.info("Calibrating with provider=%s", settings.llm_provider)

    try:
        samples = _build_samples(provider, judge_system)
    except ProviderError as exc:
        LOG.warning("Provider call failed (%s) — retrying in local mode.", exc)
        provider = None
        samples = _build_samples(None, judge_system)

    _persist_samples(samples)

    if provider is None:
        scores = _judge_locally(samples)
    else:
        try:
            scores = _judge_with_provider(provider, samples, judge_system)
        except ProviderError as exc:
            LOG.warning("Judge call failed (%s) — falling back to local heuristic.", exc)
            scores = _judge_locally(samples)

    rate = _detection_rate(samples, scores)
    print(f"Detection rate: {rate:.1f}%. Gate <{GATE_THRESHOLD:.0f}% to pass.")
    if rate < GATE_THRESHOLD:
        print("PASS")
        return 0
    print("FAIL: voice is too distinguishable from corpus baseline.")
    most_flagged = sorted(
        (s for s in samples if s.is_ai),
        key=lambda s: scores.get(s.sample_id, 0),
        reverse=True,
    )
    for sample in most_flagged[:3]:
        print(f"- highest AI score: {sample.sample_id} = {scores.get(sample.sample_id)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
