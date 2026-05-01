#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from common import ROOT, load_posts, save_posts
from llm_client import generate_text, get_provider, has_provider_key


KILL_PATTERNS = [
    ("its_not_just_x_its_y", "it's not just"),
    ("in_a_world_where", "in a world where"),
    ("lets_explore", "let's explore"),
    ("lets_dive_into", "let's dive into"),
    ("choice_is_yours", "the choice is yours"),
]


def infer_post_id(path: Path) -> str | None:
    stem = path.stem
    return stem.rsplit("_v", 1)[0] if "_v" in stem else None


def local_detect(draft: str) -> dict:
    flags = []
    lines = draft.splitlines()
    for idx, line in enumerate(lines, start=1):
        low = line.lower()
        for name, needle in KILL_PATTERNS:
            if needle in low:
                flags.append(
                    {
                        "pattern": name,
                        "snippet": line.strip(),
                        "line_approx": idx,
                    }
                )
        if "—" in line:
            flags.append(
                {
                    "pattern": "em_dash_style_flourish",
                    "snippet": line.strip(),
                    "line_approx": idx,
                }
            )
    return {"flags": flags, "passed": len(flags) == 0}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI tells detector")
    parser.add_argument("draft_path", help="Path to draft markdown")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use local regex-based detector",
    )
    args = parser.parse_args()

    draft_path = Path(args.draft_path)
    if not draft_path.exists():
        raise SystemExit(f"Draft not found: {draft_path}")

    load_dotenv(ROOT / ".env")
    provider = get_provider()
    has_key = has_provider_key(provider)
    draft = draft_path.read_text(encoding="utf-8")

    if args.mock or not has_key:
        result = local_detect(draft)
    else:
        prompt_tpl = (ROOT / "prompts" / "ai_tells_detector_prompt.md").read_text()
        kill_list = (ROOT / "voice" / "ai_tells_killlist.md").read_text()
        prompt = prompt_tpl.replace(
            "{{ kill_list }}", kill_list
        ).replace("{{ draft_text }}", draft)
        system = "Return ONLY valid JSON with fields: flags (array), passed (bool)."
        text = generate_text(system, prompt, max_tokens=1200)
        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            print("Detector returned non-JSON response")
            print(text)
            raise SystemExit(2) from exc

    flags = result.get("flags", [])
    passed = bool(result.get("passed")) and not flags

    post_id = infer_post_id(draft_path)
    posts = load_posts()
    if post_id:
        for post in posts:
            if post.post_id == post_id:
                post.ai_tells_check_passed = passed
                if passed:
                    post.status = "ai_tells_pass"
                break
        save_posts(posts)

    if passed:
        print("PASS")
        return

    for flag in flags:
        print(
            f"FAIL {flag.get('pattern')} @~{flag.get('line_approx')}: "
            f"{flag.get('snippet')}"
        )
    raise SystemExit(1)


if __name__ == "__main__":
    main()
