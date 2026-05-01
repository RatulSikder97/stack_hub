#!/usr/bin/env python3
"""Report whether the cadence target is on track."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from pipeline.config import get_settings
from pipeline.models import PostRecord, PostStatus
from pipeline.repository import PostRepository


class CadenceStatus(StrEnum):
    ON_TRACK = "ON TRACK"
    SLIPPING = "SLIPPING"
    LATE = "LATE"


@dataclass(frozen=True)
class CadenceReport:
    status: CadenceStatus
    days_since_last: float | None
    cadence_days: int

    def render(self) -> str:
        if self.days_since_last is None:
            return f"Status: {self.status} (no published posts yet)"
        return (
            f"Days since last published: {self.days_since_last:.1f}\n"
            f"Status: {self.status} (target cadence={self.cadence_days}d)"
        )


def evaluate(posts: list[PostRecord], cadence_days: int) -> CadenceReport:
    published = [p for p in posts if p.status == PostStatus.PUBLISHED and p.published_at]
    if not published:
        return CadenceReport(
            status=CadenceStatus.LATE,
            days_since_last=None,
            cadence_days=cadence_days,
        )
    last = max(published, key=lambda p: p.published_at or "")
    assert last.published_at is not None
    ts = datetime.fromisoformat(last.published_at)
    days = (datetime.now(timezone.utc) - ts).total_seconds() / 86400
    if days <= cadence_days:
        status = CadenceStatus.ON_TRACK
    elif days <= cadence_days * 1.5:
        status = CadenceStatus.SLIPPING
    else:
        status = CadenceStatus.LATE
    return CadenceReport(
        status=status, days_since_last=days, cadence_days=cadence_days
    )


def main() -> int:
    settings = get_settings()
    posts = PostRepository().list()
    report = evaluate(posts, settings.cadence_days)
    print(report.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
