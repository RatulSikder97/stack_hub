"""PostRepository CRUD + atomic writes."""

from __future__ import annotations

import json

import pytest

from pipeline.models import PostRecord, PostStatus
from pipeline.repository import PostNotFoundError, PostRepository


def test_repository_round_trip(tmp_project) -> None:  # noqa: ANN001
    repo = PostRepository()
    assert repo.list() == []

    post = PostRecord(post_id="20260501-a", working_title="Alpha")
    repo.append(post)

    assert repo.exists("20260501-a")
    assert repo.get("20260501-a").working_title == "Alpha"


def test_repository_rejects_duplicate(tmp_project) -> None:  # noqa: ANN001
    repo = PostRepository()
    repo.append(PostRecord(post_id="20260501-a"))
    with pytest.raises(ValueError, match="Duplicate post_id"):
        repo.append(PostRecord(post_id="20260501-a"))


def test_repository_update_partial(tmp_project) -> None:  # noqa: ANN001
    repo = PostRepository()
    repo.append(PostRecord(post_id="20260501-a"))
    updated = repo.update("20260501-a", status=PostStatus.DRAFTING, share_count=4)
    assert updated.status is PostStatus.DRAFTING
    assert updated.share_count == 4
    # Confirm round-trip persisted.
    assert repo.get("20260501-a").share_count == 4


def test_repository_update_missing_raises(tmp_project) -> None:  # noqa: ANN001
    repo = PostRepository()
    with pytest.raises(PostNotFoundError):
        repo.update("missing", share_count=1)


def test_repository_recent_published_orders_by_published_at(tmp_project) -> None:  # noqa: ANN001
    repo = PostRepository()
    repo.append(
        PostRecord(
            post_id="20260101-a",
            status=PostStatus.PUBLISHED,
            published_at="2026-01-01T00:00:00+00:00",
        )
    )
    repo.append(
        PostRecord(
            post_id="20260301-c",
            status=PostStatus.PUBLISHED,
            published_at="2026-03-01T00:00:00+00:00",
        )
    )
    repo.append(
        PostRecord(
            post_id="20260201-b",
            status=PostStatus.PUBLISHED,
            published_at="2026-02-01T00:00:00+00:00",
        )
    )
    ids = [p.post_id for p in repo.recent_published(3)]
    assert ids == ["20260301-c", "20260201-b", "20260101-a"]


def test_atomic_write_no_partial_file(tmp_project) -> None:  # noqa: ANN001
    repo = PostRepository()
    repo.append(PostRecord(post_id="20260501-a"))
    raw = json.loads(repo.path.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert raw[0]["post_id"] == "20260501-a"
