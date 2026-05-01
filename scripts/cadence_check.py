#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone

from common import load_config, load_posts


def main() -> None:
    posts = [p for p in load_posts() if p.status == "published" and p.published_at]
    config = load_config()
    cadence_days = int(config.get("cadence_days", 7))

    if not posts:
        print("Status: LATE (no published posts yet)")
        return

    last = max(posts, key=lambda p: p.published_at or "")
    ts = datetime.fromisoformat(last.published_at)
    days = (datetime.now(timezone.utc) - ts).total_seconds() / 86400

    if days <= cadence_days:
        status = "ON TRACK"
    elif days <= cadence_days * 1.5:
        status = "SLIPPING"
    else:
        status = "LATE"

    print(f"Days since last published: {days:.1f}")
    print(f"Status: {status}")


if __name__ == "__main__":
    main()
