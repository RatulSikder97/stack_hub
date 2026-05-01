"""health_check signal collection + report rendering."""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone


def _published_post(post_id: str, hook: str, framework: str, days_ago: int):  # noqa: ANN201
    from pipeline.models import PostRecord, PostStatus

    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return PostRecord(
        post_id=post_id,
        status=PostStatus.PUBLISHED,
        hook_pattern_used=hook,
        structural_framework_used=framework,
        published_at=ts.isoformat(),
        ai_tells_check_passed=True,
        human_edit_completed=True,
    )


def test_collect_signals_with_data(tmp_project) -> None:  # noqa: ANN001
    from pipeline.repository import PostRepository

    repo = PostRepository()
    repo.append(_published_post("a", "Counterintuitive Open", "The Reversal", 1))
    repo.append(_published_post("b", "Confession", "The Concept Lens", 2))

    import health_check

    importlib.reload(health_check)
    signals = health_check.collect_signals()
    labels = {s.label for s in signals}
    assert "Rotation diversity" in labels
    assert "Cadence" in labels
    assert "AI-tells flag rate (last 10)" in labels
    assert "Retention pass rate (last 10)" in labels


def test_main_writes_health_file(tmp_project) -> None:  # noqa: ANN001
    import health_check

    importlib.reload(health_check)
    rc = health_check.main()
    assert rc == 0
    files = list((tmp_project / "rituals" / "audits").glob("*_health.md"))
    assert files
