#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone

from common import PostRecord, ROOT, load_posts, now_iso, save_posts


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
    return re.sub(r"[\s_-]+", "-", cleaned)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new post brief")
    parser.add_argument("--title", required=True, help="Working title")
    args = parser.parse_args()

    post_id = f"{datetime.now(timezone.utc):%Y%m%d}-{slugify(args.title)}"
    briefs_dir = ROOT / "briefs"
    template = (briefs_dir / "_TEMPLATE.md").read_text()

    posts = load_posts()
    last_published = [p for p in posts if p.status == "published"][-3:]
    hooks = [p.hook_pattern_used for p in last_published if p.hook_pattern_used]
    frameworks = [p.structural_framework_used for p in last_published if p.structural_framework_used]

    rotation = (
        "\n\n### Rotation Snapshot\n"
        f"- Last 3 hook patterns: {hooks or ['none']}\n"
        f"- Last 3 frameworks: {frameworks or ['none']}\n"
    )

    brief_path = briefs_dir / f"{post_id}.md"
    brief_path.write_text(f"# {post_id}\n\n{template}{rotation}")

    record = PostRecord(post_id=post_id, working_title=args.title, status="brief", created_at=now_iso())
    posts.append(record)
    save_posts(posts)

    print(brief_path)


if __name__ == "__main__":
    main()
