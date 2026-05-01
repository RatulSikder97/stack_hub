#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import ROOT, get_post, load_posts, now_iso, save_posts


def latest_draft(post_id: str) -> Path | None:
    matches = sorted((ROOT / "drafts").glob(f"{post_id}_v*.md"))
    return matches[-1] if matches else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Log published post")
    parser.add_argument("--post-id", required=True)
    args = parser.parse_args()

    posts = load_posts()
    post = get_post(posts, args.post_id)

    if not post.ai_tells_check_passed:
        raise SystemExit("Cannot publish: ai_tells_check_passed=false")
    if not post.human_edit_completed:
        raise SystemExit("Cannot publish: human_edit_completed=false")

    url = input("Substack URL: ").strip()
    if not url.startswith("http"):
        raise SystemExit("Invalid URL")

    draft = latest_draft(args.post_id)
    if not draft:
        raise SystemExit("No draft file found to move")

    dest = ROOT / "published" / draft.name
    draft.rename(dest)

    post.status = "published"
    post.substack_url = url
    post.published_at = now_iso()
    save_posts(posts)
    print(f"Published {args.post_id} -> {url}")


if __name__ == "__main__":
    main()
