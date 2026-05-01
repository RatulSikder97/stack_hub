#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import get_post, load_posts, save_posts


def main() -> None:
    parser = argparse.ArgumentParser(description="Log post metrics")
    parser.add_argument("--post-id", required=True)
    parser.add_argument("--open-rate", required=True, type=float)
    parser.add_argument("--share-count", required=True, type=int)
    args = parser.parse_args()

    posts = load_posts()
    post = get_post(posts, args.post_id)
    post.open_rate = args.open_rate
    post.share_count = args.share_count
    save_posts(posts)
    print(f"Metrics updated for {args.post_id}")


if __name__ == "__main__":
    main()
