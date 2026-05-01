#!/usr/bin/env python3
"""Run the AI-tells detector on a draft.

Uses the LLM judge if a provider key is available; otherwise falls back to
the local kill-list detector. Either way, every flag is reported and the
post record's `ai_tells_check_passed` is updated.

Exit codes: 0 = pass, 1 = flags found, 2 = bad input.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.config import get_settings
from pipeline.detectors import DetectionResult, Detector, LocalKillListDetector
from pipeline.detectors.llm_judge import DetectorParseError, LLMJudgeDetector
from pipeline.llm import MissingAPIKeyError, build_provider
from pipeline.logging_config import get_logger
from pipeline.models import PostStatus
from pipeline.repository import PostNotFoundError, PostRepository

LOG = get_logger(__name__)


def infer_post_id(path: Path) -> str | None:
    stem = path.stem
    if "_v" not in stem:
        return None
    candidate = stem.rsplit("_v", 1)[0]
    return candidate or None


def select_detector(use_mock: bool) -> Detector:
    if use_mock:
        return LocalKillListDetector()
    settings = get_settings()
    if not settings.has_active_provider_key():
        LOG.info(
            "No %s key set — using local kill-list detector.",
            settings.llm_provider,
        )
        return LocalKillListDetector()
    try:
        provider = build_provider(settings)
    except MissingAPIKeyError:
        return LocalKillListDetector()
    return LLMJudgeDetector(
        provider=provider,
        max_tokens=settings.llm_max_tokens_detector,
    )


def update_post_status(post_id: str | None, result: DetectionResult) -> None:
    if not post_id:
        return
    repo = PostRepository()
    try:
        post = repo.get(post_id)
    except PostNotFoundError:
        LOG.debug("Detector ran on draft without matching post record: %s", post_id)
        return
    if result.passed:
        new_status = PostStatus.AI_TELLS_PASS
    elif post.status == PostStatus.AI_TELLS_PASS:
        # Previously passed, now failing — demote so the workflow sees it
        # as a draft that needs revision again.
        new_status = PostStatus.DRAFTING
    else:
        new_status = post.status
    repo.update(
        post.post_id,
        ai_tells_check_passed=result.passed,
        status=new_status,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AI-tells detector")
    parser.add_argument("draft_path", help="Path to draft markdown")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force the local kill-list detector even if a provider key is set.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    draft_path = Path(args.draft_path)
    if not draft_path.exists():
        LOG.error("Draft not found: %s", draft_path)
        return 2

    draft = draft_path.read_text(encoding="utf-8")
    detector = select_detector(args.mock)
    LOG.info("Detector: %s", type(detector).__name__)

    try:
        result = detector.detect(draft)
    except DetectorParseError as exc:
        LOG.error("Detector parse error: %s", exc)
        return 2

    update_post_status(infer_post_id(draft_path), result)

    if result.passed:
        print("PASS")
        return 0

    for flag in result.flags:
        print(f"FAIL {flag.pattern} @~{flag.line_approx}: {flag.snippet}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
