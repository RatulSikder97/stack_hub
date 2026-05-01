#!/usr/bin/env python3
"""Update share count + open rate on an existing post record."""

from __future__ import annotations

import argparse
import sys

from pipeline.logging_config import get_logger
from pipeline.repository import PostNotFoundError, PostRepository

LOG = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log post metrics")
    parser.add_argument("--post-id", required=True)
    parser.add_argument("--open-rate", required=True, type=float)
    parser.add_argument("--share-count", required=True, type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.open_rate < 0 or args.open_rate > 100:
        LOG.error("--open-rate must be in [0, 100], got %.2f", args.open_rate)
        return 2
    if args.share_count < 0:
        LOG.error("--share-count must be >= 0")
        return 2

    repo = PostRepository()
    try:
        repo.update(
            args.post_id,
            open_rate=args.open_rate,
            share_count=args.share_count,
        )
    except PostNotFoundError:
        LOG.error("post_id not found: %s", args.post_id)
        return 2

    print(
        f"Metrics updated for {args.post_id}: "
        f"open_rate={args.open_rate}, share_count={args.share_count}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
