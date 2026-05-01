"""pattern_audit report builder."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pipeline.models import PostRecord, PostStatus


def _published_post(post_id: str, days_ago: int, hook: str, framework: str) -> PostRecord:
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return PostRecord(
        post_id=post_id,
        status=PostStatus.PUBLISHED,
        hook_pattern_used=hook,
        structural_framework_used=framework,
        published_at=ts.isoformat(),
        open_rate=42.0,
        share_count=10,
    )


def test_build_report_excludes_outside_window(tmp_project) -> None:  # noqa: ANN001
    from pattern_audit import build_report

    posts = [
        _published_post("a", 5, "Confession", "The Reversal"),
        _published_post("b", 60, "Tiny Story", "The Letter"),
    ]
    report, summary = build_report(posts, window_days=30)
    assert summary["published_count"] == 1
    assert "Confession" in report
    assert "Tiny Story" not in report.split("Hook counts")[1].split("##")[0]


def test_overused_threshold(tmp_project) -> None:  # noqa: ANN001
    from pattern_audit import build_report

    posts = [
        _published_post(f"id{i}", 1, "Confession", "The Reversal") for i in range(5)
    ]
    _report, summary = build_report(posts, window_days=30)
    assert summary["overused_hooks"] == ["Confession"]
    assert summary["overused_frameworks"] == ["The Reversal"]


def test_main_writes_audit_file(tmp_project) -> None:  # noqa: ANN001
    import pattern_audit

    rc = pattern_audit.main([])
    assert rc == 0
    audit_dir = tmp_project / "rituals" / "audits"
    files = list(audit_dir.glob("*_pattern_audit.md"))
    assert files
