"""cadence_check evaluator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pipeline.models import PostRecord, PostStatus


def _published(days_ago: float) -> PostRecord:
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return PostRecord(
        post_id=f"id-{days_ago}",
        status=PostStatus.PUBLISHED,
        published_at=ts.isoformat(),
    )


def test_no_posts_is_late(tmp_project) -> None:  # noqa: ANN001
    from cadence_check import CadenceStatus, evaluate

    report = evaluate([], 7)
    assert report.status is CadenceStatus.LATE
    assert report.days_since_last is None


def test_recent_post_on_track(tmp_project) -> None:  # noqa: ANN001
    from cadence_check import CadenceStatus, evaluate

    report = evaluate([_published(2)], 7)
    assert report.status is CadenceStatus.ON_TRACK


def test_slipping_window(tmp_project) -> None:  # noqa: ANN001
    from cadence_check import CadenceStatus, evaluate

    report = evaluate([_published(9)], 7)
    assert report.status is CadenceStatus.SLIPPING


def test_late_window(tmp_project) -> None:  # noqa: ANN001
    from cadence_check import CadenceStatus, evaluate

    report = evaluate([_published(20)], 7)
    assert report.status is CadenceStatus.LATE


def test_render_no_posts(tmp_project) -> None:  # noqa: ANN001
    from cadence_check import CadenceStatus, CadenceReport

    text = CadenceReport(
        status=CadenceStatus.LATE, days_since_last=None, cadence_days=7
    ).render()
    assert "no published posts yet" in text
