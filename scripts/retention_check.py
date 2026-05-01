#!/usr/bin/env python3
"""Run the human retention checklist interactively.

All four questions must answer "yes" for the post to advance to
`retention_check`. A single "no" demotes status back to `editing`.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from pipeline.logging_config import get_logger
from pipeline.models import PostStatus, RetentionAnswer
from pipeline.repository import PostNotFoundError, PostRepository

LOG = get_logger(__name__)

QUESTIONS: tuple[str, ...] = (
    "Open loop set in para 2, resolved in para 6+?",
    "Pattern interrupts every 200-300 words (one-line para, question, fragment)?",
    "Buried 'wait, what?' sentence two-thirds in?",
    "Closing line screenshot-able after deliberate revision?",
)


def ask_yes_no(question: str, *, prompt_fn: Callable[[str], str] = input) -> bool:
    while True:
        raw = prompt_fn(f"{question} [y/n]: ").strip().lower()
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False


def collect_answers(
    *, prompt_fn: Callable[[str], str] = input
) -> list[RetentionAnswer]:
    return [
        RetentionAnswer(question=q, passed=ask_yes_no(q, prompt_fn=prompt_fn))
        for q in QUESTIONS
    ]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run retention check interactively")
    parser.add_argument("--post-id", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = PostRepository()

    try:
        repo.get(args.post_id)
    except PostNotFoundError:
        LOG.error("post_id not found: %s", args.post_id)
        return 2

    answers = collect_answers()
    all_yes = all(answer.passed for answer in answers)
    new_status = PostStatus.RETENTION_CHECK if all_yes else PostStatus.EDITING

    repo.update(
        args.post_id,
        retention_check_answers=answers,
        human_edit_completed=all_yes,
        status=new_status,
    )

    print("PASS" if all_yes else "FAIL")
    return 0 if all_yes else 1


if __name__ == "__main__":
    sys.exit(main())
