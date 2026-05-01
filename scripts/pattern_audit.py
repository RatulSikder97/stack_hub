#!/usr/bin/env python3
"""30-day pattern audit — counts hooks/frameworks and computes performance."""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from pipeline import paths as _paths
from pipeline.logging_config import get_logger
from pipeline.models import PostRecord, PostStatus
from pipeline.paths import ensure_dirs
from pipeline.repository import PostRepository

LOG = get_logger(__name__)

OVERUSED_THRESHOLD = 3


def _published_within(posts: list[PostRecord], days: int) -> list[PostRecord]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out: list[PostRecord] = []
    for post in posts:
        if post.status != PostStatus.PUBLISHED or not post.published_at:
            continue
        try:
            ts = datetime.fromisoformat(post.published_at)
        except ValueError:
            continue
        if ts >= cutoff:
            out.append(post)
    return out


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _format_counts(counter: Counter[str]) -> list[str]:
    if not counter:
        return ["- (none)"]
    return [f"- {key}: {value}" for key, value in counter.most_common()]


def _format_perf(perf: dict[str, dict[str, list[float]]]) -> list[str]:
    if not perf:
        return ["- (none)"]
    return [
        f"- {key}: avg_open_rate={_avg(metrics['open']):.2f}, "
        f"avg_share_count={_avg(metrics['share']):.2f}"
        for key, metrics in perf.items()
    ]


def build_report(posts: list[PostRecord], window_days: int) -> tuple[str, dict]:
    published = _published_within(posts, window_days)

    hook_counts: Counter[str] = Counter(
        p.hook_pattern_used for p in published if p.hook_pattern_used
    )
    framework_counts: Counter[str] = Counter(
        p.structural_framework_used for p in published if p.structural_framework_used
    )

    hook_perf: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"open": [], "share": []}
    )
    framework_perf: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"open": [], "share": []}
    )
    for post in published:
        if post.hook_pattern_used:
            hook_perf[post.hook_pattern_used]["open"].append(post.open_rate)
            hook_perf[post.hook_pattern_used]["share"].append(float(post.share_count))
        if post.structural_framework_used:
            framework_perf[post.structural_framework_used]["open"].append(post.open_rate)
            framework_perf[post.structural_framework_used]["share"].append(
                float(post.share_count)
            )

    overused_hooks = [k for k, v in hook_counts.items() if v > OVERUSED_THRESHOLD]
    overused_frameworks = [
        k for k, v in framework_counts.items() if v > OVERUSED_THRESHOLD
    ]
    underused_hooks = [k for k, v in hook_counts.items() if v == 0]
    underused_frameworks = [k for k, v in framework_counts.items() if v == 0]

    month_tag = datetime.now(timezone.utc).strftime("%Y-%m")
    report = "\n".join(
        [
            f"# Pattern Audit - {month_tag}",
            "",
            f"Published posts (last {window_days}d): {len(published)}",
            "",
            "## Hook counts",
            *_format_counts(hook_counts),
            "",
            "## Framework counts",
            *_format_counts(framework_counts),
            "",
            "## Hook performance",
            *_format_perf(hook_perf),
            "",
            "## Framework performance",
            *_format_perf(framework_perf),
            "",
            f"Over-used hooks (>{OVERUSED_THRESHOLD}): {overused_hooks or ['none']}",
            f"Over-used frameworks (>{OVERUSED_THRESHOLD}): "
            f"{overused_frameworks or ['none']}",
            f"Under-used hooks (0): {underused_hooks or ['none']}",
            f"Under-used frameworks (0): {underused_frameworks or ['none']}",
        ]
    )

    summary = {
        "published_count": len(published),
        "overused_hooks": overused_hooks,
        "overused_frameworks": overused_frameworks,
        "underused_hooks": underused_hooks,
        "underused_frameworks": underused_frameworks,
    }
    return report + "\n", summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="30-day hook+framework audit")
    parser.add_argument("--window-days", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_dirs()
    posts = PostRepository().list()
    report, _summary = build_report(posts, args.window_days)

    month_tag = datetime.now(timezone.utc).strftime("%Y-%m")
    out = _paths.AUDITS_DIR / f"{month_tag}_pattern_audit.md"
    out.write_text(report, encoding="utf-8")
    LOG.info("Audit written: %s", out)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
