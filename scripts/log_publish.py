#!/usr/bin/env python3
"""Mark a post as published, capture the Substack URL, and move the draft.

Refuses to publish unless both gates passed:
* `ai_tells_check_passed = true`
* `human_edit_completed = true`

URLs containing `example.com` are rejected explicitly so we never log a
placeholder URL into a production record.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from pipeline import paths as _paths
from pipeline.logging_config import get_logger
from pipeline.models import PostStatus, now_iso
from pipeline.paths import ensure_dirs
from pipeline.repository import PostNotFoundError, PostRepository

LOG = get_logger(__name__)


class PublishGateError(RuntimeError):
    """Raised when a publish prerequisite is not met."""


def latest_draft(post_id: str, drafts_dir: Path | None = None) -> Path | None:
    drafts_dir = drafts_dir if drafts_dir is not None else _paths.DRAFTS_DIR
    matches = sorted(drafts_dir.glob(f"{post_id}_v*.md"))
    return matches[-1] if matches else None


def validate_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        raise PublishGateError(
            f"Invalid Substack URL: {url!r} (must start with http:// or https://)"
        )
    if "example.com" in url or "example.substack.com" in url:
        raise PublishGateError(
            f"Refusing placeholder URL: {url!r} (contains example.com)"
        )
    return url


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log published post")
    parser.add_argument("--post-id", required=True)
    parser.add_argument(
        "--url",
        help="Substack URL (avoids interactive prompt; useful for scripts)",
    )
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    *,
    prompt_fn: Callable[[str], str] = input,
) -> int:
    args = parse_args(argv)
    ensure_dirs()
    repo = PostRepository()

    try:
        post = repo.get(args.post_id)
    except PostNotFoundError:
        LOG.error("post_id not found: %s", args.post_id)
        return 2

    if not post.ai_tells_check_passed:
        LOG.error("Cannot publish: ai_tells_check_passed=false")
        return 1
    if not post.human_edit_completed:
        LOG.error("Cannot publish: human_edit_completed=false")
        return 1

    raw_url = args.url if args.url is not None else prompt_fn("Substack URL: ")
    try:
        url = validate_url(raw_url)
    except PublishGateError as exc:
        LOG.error("%s", exc)
        return 1

    draft = latest_draft(args.post_id)
    if draft is None:
        LOG.error("No draft file found to publish for %s", args.post_id)
        return 1

    dest = _paths.PUBLISHED_DIR / draft.name
    draft.replace(dest)

    repo.update(
        post.post_id,
        status=PostStatus.PUBLISHED,
        substack_url=url,
        published_at=now_iso(),
    )

    LOG.info("Published %s -> %s", post.post_id, url)
    print(f"Published {post.post_id} -> {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
