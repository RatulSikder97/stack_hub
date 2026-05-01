#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from common import ROOT, load_posts


def main() -> None:
    posts = load_posts()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)

    published = []
    for p in posts:
        if p.status != "published" or not p.published_at:
            continue
        try:
            ts = datetime.fromisoformat(p.published_at)
        except ValueError:
            continue
        if ts >= cutoff:
            published.append(p)

    hook_counts = Counter(p.hook_pattern_used for p in published if p.hook_pattern_used)
    fw_counts = Counter(p.structural_framework_used for p in published if p.structural_framework_used)

    hook_perf = defaultdict(lambda: {"open": [], "share": []})
    fw_perf = defaultdict(lambda: {"open": [], "share": []})
    for p in published:
        if p.hook_pattern_used:
            hook_perf[p.hook_pattern_used]["open"].append(p.open_rate)
            hook_perf[p.hook_pattern_used]["share"].append(p.share_count)
        if p.structural_framework_used:
            fw_perf[p.structural_framework_used]["open"].append(p.open_rate)
            fw_perf[p.structural_framework_used]["share"].append(p.share_count)

    def avg(xs):
        return round(sum(xs) / len(xs), 2) if xs else 0.0

    over_used_hooks = [k for k, v in hook_counts.items() if v > 3]
    over_used_fws = [k for k, v in fw_counts.items() if v > 3]

    month_tag = now.strftime("%Y-%m")
    out = ROOT / "rituals" / "audits" / f"{month_tag}_pattern_audit.md"

    lines = [f"# Pattern Audit - {month_tag}", "", f"Published posts (30d): {len(published)}", "", "## Hook counts"]
    lines += [f"- {k}: {v}" for k, v in hook_counts.items()] or ["- none"]
    lines += ["", "## Framework counts"]
    lines += [f"- {k}: {v}" for k, v in fw_counts.items()] or ["- none"]
    lines += ["", "## Hook performance"]
    lines += [f"- {k}: avg_open_rate={avg(v['open'])}, avg_share_count={avg(v['share'])}" for k, v in hook_perf.items()] or ["- none"]
    lines += ["", "## Framework performance"]
    lines += [f"- {k}: avg_open_rate={avg(v['open'])}, avg_share_count={avg(v['share'])}" for k, v in fw_perf.items()] or ["- none"]
    lines += ["", f"Over-used hooks (>3): {over_used_hooks or ['none']}"]
    lines += [f"Over-used frameworks (>3): {over_used_fws or ['none']}"]

    out.write_text("\n".join(lines) + "\n")
    print(f"Audit written: {out}")


if __name__ == "__main__":
    main()
