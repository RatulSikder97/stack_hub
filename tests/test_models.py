"""Pydantic model invariants."""

from __future__ import annotations

import pytest

from pipeline.models import PostRecord, PostStatus, RetentionAnswer


def test_post_record_defaults() -> None:
    post = PostRecord(post_id="20260501-test")
    assert post.status is PostStatus.IDEA
    assert post.ai_tells_check_passed is False
    assert post.share_count == 0
    assert post.open_rate == 0.0
    assert post.retention_check_answers == []


def test_post_record_rejects_blank_id() -> None:
    with pytest.raises(ValueError, match="post_id must not be empty"):
        PostRecord(post_id="   ")


def test_post_record_rejects_bad_url() -> None:
    with pytest.raises(ValueError, match="must start with"):
        PostRecord(post_id="20260501-x", substack_url="ftp://example.com")


def test_with_status_returns_copy() -> None:
    post = PostRecord(post_id="20260501-x")
    updated = post.with_status(PostStatus.PUBLISHED)
    assert updated.status is PostStatus.PUBLISHED
    assert post.status is PostStatus.IDEA  # original unchanged


def test_open_rate_bounds() -> None:
    with pytest.raises(ValueError):
        PostRecord(post_id="20260501-x", open_rate=120.0)


def test_retention_answer_extra_forbidden() -> None:
    with pytest.raises(ValueError):
        RetentionAnswer(question="Q", passed=True, extra="nope")  # type: ignore[call-arg]
