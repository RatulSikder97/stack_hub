#!/usr/bin/env python3
"""Create a new post brief from the template and append a `PostRecord`.

Reads `briefs/_TEMPLATE.md`, prefills the rotation snapshot from the last 3
published posts, and appends a `status="brief"` record to `data/posts.json`.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone

from pipeline import paths as _paths
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
    parser.add_argument("--title", required=True, help="Working title")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_dirs()

    repo = PostRepository()
    post_id = make_post_id(args.title)

    if repo.exists(post_id):
        LOG.error("post_id already exists: %s", post_id)
        return 2

    template = _paths.BRIEF_TEMPLATE_PATH.read_text(encoding="utf-8")
    body = f"# {post_id}\n\n{template}{build_rotation_snapshot(repo)}"

    brief_path = _paths.BRIEFS_DIR / f"{post_id}.md"
    brief_path.write_text(body, encoding="utf-8")

    repo.append(
        PostRecord(
            post_id=post_id,
            working_title=args.title,
            status=PostStatus.BRIEF,
        )
    )

    LOG.info("Brief created at %s", brief_path)
    print(brief_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
