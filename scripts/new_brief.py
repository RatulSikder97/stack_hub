#!/usr/bin/env python3
"""Create a new post brief.

Two modes:

* ``--title "..."`` — empty template + rotation snapshot. The strategist
  fills One Big Idea, Why, hook, framework manually.
* ``--from-idea "..."`` — accepts a raw idea in any language. Translates
  to English (preserving the original in the brief) and asks the LLM to
  populate working title plus all six strategic sections, anchored on
  the brand voice.

Both modes append a ``status="brief"`` record to ``data/posts.json``.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone

from pipeline import paths as _paths
from pipeline.brief_builder import BriefBuildError, BriefDraft, IdeaToBrief
from pipeline.config import get_settings
from pipeline.llm import MissingAPIKeyError, build_provider
from pipeline.logging_config import get_logger
from pipeline.models import PostRecord, PostStatus
from pipeline.paths import ensure_dirs
from pipeline.repository import PostRepository

LOG = get_logger(__name__)

_SLUG_RE = re.compile(r"[^a-zA-Z0-9\s-]+")
_SPACE_RE = re.compile(r"[\s_-]+")


def slugify(text: str) -> str:
    cleaned = _SLUG_RE.sub("", text).strip().lower()
    slug = _SPACE_RE.sub("-", cleaned)
    return slug.strip("-")


def build_rotation_snapshot(repo: PostRepository) -> str:
    last_three = repo.recent_published(3)
    hooks = [p.hook_pattern_used for p in last_three if p.hook_pattern_used] or ["none"]
    frameworks = [
        p.structural_framework_used for p in last_three if p.structural_framework_used
    ] or ["none"]
    return (
        "\n\n### Rotation Snapshot (auto-filled)\n"
        f"- Last 3 hook patterns: {hooks}\n"
        f"- Last 3 frameworks: {frameworks}\n"
    )


def make_post_id(title: str, today: datetime | None = None) -> str:
    today = today or datetime.now(timezone.utc)
    slug = slugify(title)
    if not slug:
        raise ValueError(f"Title produces empty slug: {title!r}")
    return f"{today:%Y%m%d}-{slug}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a new post brief")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--title", help="Working title (manual brief mode)")
    group.add_argument(
        "--from-idea",
        dest="from_idea",
        help="Raw idea in any language. Translates + auto-populates the brief.",
    )
    parser.add_argument(
        "--target-language",
        default="en",
        help="Target working language (default: en)",
    )
    return parser.parse_args(argv)


def _write_manual_brief(repo: PostRepository, title: str) -> int:
    post_id = make_post_id(title)
    if repo.exists(post_id):
        LOG.error("post_id already exists: %s", post_id)
        return 2

    template = _paths.BRIEF_TEMPLATE_PATH.read_text(encoding="utf-8")
    body = f"# {post_id}\n\n{template}{build_rotation_snapshot(repo)}"
    brief_path = _paths.BRIEFS_DIR / f"{post_id}.md"
    brief_path.write_text(body, encoding="utf-8")

    repo.append(
        PostRecord(post_id=post_id, working_title=title, status=PostStatus.BRIEF)
    )
    LOG.info("Brief created at %s", brief_path)
    print(brief_path)
    return 0


def _write_idea_brief(repo: PostRepository, idea: str, target_language: str) -> int:
    settings = get_settings()
    if not settings.has_active_provider_key():
        LOG.error(
            "--from-idea requires a configured LLM provider. "
            "Set the API key for provider=%s in .env.",
            settings.llm_provider,
        )
        return 2

    try:
        provider = build_provider(settings)
    except MissingAPIKeyError as exc:
        LOG.error("%s", exc)
        return 2

    composer = IdeaToBrief(provider=provider, max_tokens=settings.llm_max_tokens_voice)

    LOG.info("Composing brief from idea via %s …", settings.llm_provider)
    try:
        draft = composer.build(idea, target_language=target_language)
    except BriefBuildError as exc:
        LOG.error("Brief composition failed: %s", exc)
        return 1

    if not draft.working_title:
        LOG.error("LLM returned empty working title — aborting.")
        return 1

    post_id = make_post_id(draft.working_title)
    if repo.exists(post_id):
        LOG.error("post_id already exists: %s", post_id)
        return 2

    body = (
        f"# {post_id}\n\n"
        f"{draft.render()}"
        f"{build_rotation_snapshot(repo)}"
    )
    brief_path = _paths.BRIEFS_DIR / f"{post_id}.md"
    brief_path.write_text(body, encoding="utf-8")

    repo.append(
        PostRecord(
            post_id=post_id,
            working_title=draft.working_title,
            status=PostStatus.BRIEF,
            hook_pattern_used=draft.target_hook,
            structural_framework_used=draft.target_framework,
        )
    )
    _print_idea_summary(draft)
    print(brief_path)
    return 0


def _print_idea_summary(draft: BriefDraft) -> None:
    """Show the user a short readable summary of what was composed."""
    bar = "─" * 60
    print(bar, file=sys.stderr)
    if draft.translation and draft.translation.needed_translation:
        print(
            f"Source language : {draft.translation.source_language}",
            file=sys.stderr,
        )
        print(
            f"Translation     : {draft.translation.translated_text[:120]}…"
            if len(draft.translation.translated_text) > 120
            else f"Translation     : {draft.translation.translated_text}",
            file=sys.stderr,
        )
    print(f"Working title   : {draft.working_title}", file=sys.stderr)
    print(f"Hook pattern    : {draft.target_hook}", file=sys.stderr)
    print(f"Framework       : {draft.target_framework}", file=sys.stderr)
    print(bar, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_dirs()
    repo = PostRepository()

    if args.from_idea:
        return _write_idea_brief(repo, args.from_idea, args.target_language)
    return _write_manual_brief(repo, args.title)


if __name__ == "__main__":
    sys.exit(main())
