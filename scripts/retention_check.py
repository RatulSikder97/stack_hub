#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import get_post, load_posts, save_posts

QUESTIONS = [
    "Open loop set in para 2, resolved in para 6+?",
    "Pattern interrupts every 200-300 words?",
    "Buried 'wait, what?' sentence two-thirds in?",
    "Closing line screenshot-able after deliberate revision?",
]


def ask_yes_no(question: str) -> bool:
    while True:
        raw = input(f"{question} [y/n]: ").strip().lower()
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Run retention check interactively")
    parser.add_argument("--post-id", required=True)
    args = parser.parse_args()

    posts = load_posts()
    post = get_post(posts, args.post_id)

    answers = [{"question": q, "passed": ask_yes_no(q)} for q in QUESTIONS]
    all_yes = all(item["passed"] for item in answers)

    post.retention_check_answers = answers
    post.human_edit_completed = all_yes
    post.status = "retention_check" if all_yes else "editing"
    save_posts(posts)
    print("PASS" if all_yes else "FAIL")


if __name__ == "__main__":
    main()
