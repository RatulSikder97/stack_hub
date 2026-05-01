#!/usr/bin/env python3
"""Generate a draft from a brief using the configured LLM provider.

Composes the master system prompt via real Jinja2 rendering (voice, brand
promise, kill list, rotation context all injected from disk) and ships the
brief + libraries as the user prompt.
"""

from __future__ import annotations

import argparse
import sys

from pipeline import paths as _paths
from pipeline.config import get_settings
from pipeline.llm import LLMProvider, MissingAPIKeyError, build_provider
from pipeline.logging_config import get_logger
from pipeline.models import PostStatus
from pipeline.paths import ensure_dirs
from pipeline.repository import PostNotFoundError, PostRepository
from pipeline.templating import render_master_prompt

LOG = get_logger(__name__)


_MOCK_DRAFT_TEMPLATE = """# {post_id}

You are not overwhelmed because life is unusually hard. You are overwhelmed
because too many decisions remain unresolved.

## What is actually draining you?
Unmade decisions act like background tabs in the mind. Each one costs a
little attention every hour.

## How to recover control
Pick one delayed decision, define the next irreversible step, and commit to
it today.

The calm you want is mostly a byproduct of fewer open loops.

<!-- MOCK_DRAFT generated because --mock was passed or no provider key. -->
<!-- context_chars={context_chars} -->
"""


def build_user_prompt(post_id: str) -> str:
    brief = (_paths.BRIEFS_DIR / f"{post_id}.md").read_text(encoding="utf-8")
    hooks = _paths.HOOK_LIBRARY_PATH.read_text(encoding="utf-8")
    structures = _paths.STRUCTURE_LIBRARY_PATH.read_text(encoding="utf-8")
    return (
        "Draft a post following the brief and inheriting the master prompt's "
        "constraints. Use the hook + structure libraries as a menu, not a script.\n\n"
        f"## BRIEF\n{brief}\n\n"
        f"## HOOK LIBRARY (reference)\n{hooks}\n\n"
        f"## STRUCTURE LIBRARY (reference)\n{structures}\n"
    )


def make_mock_draft(post_id: str, context: str) -> str:
    return _MOCK_DRAFT_TEMPLATE.format(post_id=post_id, context_chars=len(context))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate draft from brief")
    parser.add_argument("--post-id", required=True)
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Skip the API call and write a deterministic local draft.",
    )
    return parser.parse_args(argv)


def _resolve_provider(use_mock: bool) -> LLMProvider | None:
    if use_mock:
        return None
    settings = get_settings()
    if not settings.has_active_provider_key():
        LOG.warning(
            "No API key for provider=%s — falling back to mock draft.",
            settings.llm_provider,
        )
        return None
    try:
        return build_provider(settings)
    except MissingAPIKeyError as exc:
        LOG.warning("Provider unavailable, using mock: %s", exc)
        return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_dirs()

    settings = get_settings()
    repo = PostRepository()

    try:
        post = repo.get(args.post_id)
    except PostNotFoundError:
        LOG.error("post_id not found: %s", args.post_id)
        return 2

    rotation = repo.recent_published(3)
    system_prompt = render_master_prompt(
        brand_name=settings.brand_name, rotation=rotation
    )
    user_prompt = build_user_prompt(args.post_id)

    provider = _resolve_provider(args.mock)
    if provider is None:
        text = make_mock_draft(args.post_id, user_prompt)
    else:
        LOG.info(
            "Generating draft via %s (%s)",
            settings.llm_provider,
            provider.model,
        )
        text = provider.generate(
            system_prompt,
            user_prompt,
            max_tokens=settings.llm_max_tokens_draft,
            temperature=settings.llm_temperature,
        )

    out = _paths.DRAFTS_DIR / f"{args.post_id}_v1.md"
    out.write_text(text.rstrip() + "\n", encoding="utf-8")

    repo.update(post.post_id, status=PostStatus.DRAFTING)
    LOG.info("Draft written: %s", out)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
