#!/usr/bin/env python3
from __future__ import annotations

import argparse

from dotenv import load_dotenv

from common import ROOT, get_post, load_config, load_posts, save_posts
from llm_client import generate_text, get_provider, has_provider_key


def build_context(post_id: str) -> str:
    brief = (ROOT / "briefs" / f"{post_id}.md").read_text()
    hooks = (ROOT / "libraries" / "hook_library.md").read_text()
    structures = (ROOT / "libraries" / "structure_library.md").read_text()
    return (
        f"## BRIEF\n{brief}\n\n"
        f"## HOOKS\n{hooks}\n\n"
        f"## STRUCTURES\n{structures}"
    )


def mock_draft(post_id: str, context: str) -> str:
    return (
        f"# {post_id}\n\n"
        "You are not overwhelmed because life is unusually hard. "
        "You are overwhelmed because too many decisions remain unresolved.\n\n"
        "## What is actually draining you?\n"
        "Unmade decisions act like background tabs in the mind. "
        "Each one costs a little attention every hour.\n\n"
        "## How to recover control\n"
        "Pick one delayed decision, define the next irreversible step, and commit to it today.\n\n"
        "The calm you want is mostly a byproduct of fewer open loops.\n\n"
        "<!-- MOCK_DRAFT generated because API key or --mock mode was used. -->\n\n"
        f"Context length: {len(context)} chars\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate draft from brief")
    parser.add_argument("--post-id", required=True)
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Generate deterministic local draft without API",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    provider = get_provider()
    has_key = has_provider_key(provider)

    posts = load_posts()
    post = get_post(posts, args.post_id)

    system_prompt = (ROOT / "prompts" / "master_system_prompt.md").read_text()
    config = load_config()
    rendered = system_prompt.replace(
        "{{ brand_name }}", str(config.get("brand_name", "Brand"))
    )
    for token in [
        "brand_promise",
        "voice_synthesis",
        "anti_voice",
        "kill_list",
        "rotation_context",
    ]:
        rendered = rendered.replace(
            "{{ " + token + " }}",
            f"PENDING_{token.upper()}",
        )

    context = build_context(args.post_id)

    if args.mock or not has_key:
        text = mock_draft(args.post_id, context)
    else:
        text = generate_text(rendered, context, max_tokens=4000)

    out = ROOT / "drafts" / f"{args.post_id}_v1.md"
    out.write_text(text + "\n")

    post.status = "drafting"
    save_posts(posts)
    print(out)


if __name__ == "__main__":
    main()
