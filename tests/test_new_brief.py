"""new_brief CLI behavior."""

from __future__ import annotations

import importlib

import pytest

from pipeline.models import PostStatus
from pipeline.repository import PostRepository


@pytest.fixture
def new_brief_module(tmp_project):  # noqa: ANN001
    import new_brief
    return importlib.reload(new_brief)


def test_slugify_basic() -> None:
    import new_brief
    assert new_brief.slugify("Hello World!") == "hello-world"
    assert new_brief.slugify("  Decision Fatigue  ") == "decision-fatigue"


def test_make_post_id_uses_today_when_none(tmp_project) -> None:  # noqa: ANN001
    from datetime import datetime, timezone

    import new_brief

    fixed = datetime(2026, 5, 1, tzinfo=timezone.utc)
    assert new_brief.make_post_id("Sprint Test", today=fixed) == "20260501-sprint-test"


def test_make_post_id_blank_title_raises(tmp_project) -> None:  # noqa: ANN001
    import new_brief

    with pytest.raises(ValueError):
        new_brief.make_post_id("@@@@@")


def test_main_creates_brief_and_record(new_brief_module, tmp_project) -> None:  # noqa: ANN001
    rc = new_brief_module.main(["--title", "Sprint Test"])
    assert rc == 0

    repo = PostRepository()
    posts = repo.list()
    assert len(posts) == 1
    assert posts[0].working_title == "Sprint Test"
    assert posts[0].status is PostStatus.BRIEF
    assert posts[0].post_id.endswith("-sprint-test")

    brief_path = tmp_project / "briefs" / f"{posts[0].post_id}.md"
    body = brief_path.read_text(encoding="utf-8")
    assert "## One Big Idea" in body
    assert "Rotation Snapshot (auto-filled)" in body


def test_main_rejects_duplicate_post_id(new_brief_module, tmp_project) -> None:  # noqa: ANN001
    new_brief_module.main(["--title", "Sprint Test"])
    rc = new_brief_module.main(["--title", "Sprint Test"])
    assert rc == 2
