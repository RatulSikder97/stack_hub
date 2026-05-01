#!/usr/bin/env python3
"""One-page pipeline health check.

Aggregates four signals:
1. Rotation diversity over all published posts
2. Cadence vs. configured target
3. Average AI-tells flag rate over the last 10 records
4. Retention check pass rate over the last 10 records
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from pipeline import paths as _paths
from pipeline.config import get_settings
from pipeline.logging_config import get_logger
from pipeline.models import PostRecord, PostStatus
from pipeline.paths import ensure_dirs
from pipeline.repository import PostRepository

LOG = get_logger(__name__)


@dataclass(frozen=True)
class Signal:
    label: str
    value: str
    color: str


def _color(value: float, *, green_at: float, yellow_at: float, inverse: bool = False) -> str:
    if inverse:
        if value <= green_at:
            return "green"
        if value <= yellow_at:
            return "yellow"
        return "red"
    if value >= green_at:
        return "green"
    if value >= yellow_at:
        return "yellow"
    return "red"


def _diversity_signal(published: list[PostRecord]) -> Signal:
    diversity = len({p.hook_pattern_used for p in published if p.hook_pattern_used}) + len(
        {p.structural_framework_used for p in published if p.structural_framework_used}
    )
    color = _color(float(diversity), green_at=6, yellow_at=3)
    return Signal(label="Rotation diversity", value=str(diversity), color=color)


def _cadence_signal(posts: list[PostRecord], cadence_days: int) -> Signal:
    from cadence_check import CadenceStatus, evaluate

    report = evaluate(posts, cadence_days)
    color = {
        CadenceStatus.ON_TRACK: "green",
        CadenceStatus.SLIPPING: "yellow",
        CadenceStatus.LATE: "red",
    }[report.status]
    return Signal(label="Cadence", value=str(report.status), color=color)


def _flags_signal(recent: list[PostRecord]) -> Signal:
    if not recent:
        return Signal(label="AI-tells flag rate (last 10)", value="n/a", color="yellow")
    rate = sum(0.0 if p.ai_tells_check_passed else 1.0 for p in recent) / len(recent)
    color = _color(rate, green_at=0.2, yellow_at=0.5, inverse=True)
    return Signal(
        label="AI-tells flag rate (last 10)",
        value=f"{rate:.2f}",
        color=color,
    )


def _retention_signal(recent: list[PostRecord]) -> Signal:
    if not recent:
        return Signal(label="Retention pass rate (last 10)", value="n/a", color="yellow")
    rate = sum(1.0 if p.human_edit_completed else 0.0 for p in recent) / len(recent)
    color = _color(rate, green_at=0.8, yellow_at=0.5)
    return Signal(
        label="Retention pass rate (last 10)",
        value=f"{rate:.0%}",
        color=color,
    )


def collect_signals() -> list[Signal]:
    settings = get_settings()
    posts = PostRepository().list()
    published = [p for p in posts if p.status == PostStatus.PUBLISHED]
    recent = posts[-10:]
    return [
        _diversity_signal(published),
        _cadence_signal(posts, settings.cadence_days),
        _flags_signal(recent),
        _retention_signal(recent),
    ]


def render(signals: list[Signal]) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [f"# Health Check - {today}", ""]
    lines += [f"- {s.label}: {s.value} ({s.color})" for s in signals]
    return "\n".join(lines) + "\n"


def main() -> int:
    ensure_dirs()
    signals = collect_signals()
    out = _paths.AUDITS_DIR / f"{datetime.now(timezone.utc):%Y-%m-%d}_health.md"
    out.write_text(render(signals), encoding="utf-8")
    LOG.info("Health report written: %s", out)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
