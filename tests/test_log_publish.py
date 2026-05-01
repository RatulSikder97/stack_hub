"""log_publish gating + URL validation."""

from __future__ import annotations

import importlib

import pytest

from pipeline.models import PostRecord, PostStatus
from pipeline.repository import PostRepository


@pytest.fixture
def log_publish_module(tmp_project):  # noqa: ANN001
    import log_publish
    return importlib.reload(log_publish)


def _seed_eligible(post_id: str = "20260501-ok") -> PostRecord:
    repo = PostRepository()
    record = PostRecord(
        post_id=post_id,
        ai_tells_check_passed=True,
        human_edit_completed=True,
        status=PostStatus.RETENTION_CHECK,
    )
    repo.append(record)
    return record


def test_validate_url_rejects_non_http() -> None:
    import log_publish

    with pytest.raises(log_publish.PublishGateError):
        log_publish.validate_url("ftp://example.com")


def test_validate_url_rejects_example_com() -> None:
    import log_publish

    with pytest.raises(log_publish.PublishGateError):
        log_publish.validate_url("https://example.substack.com/p/x")


def test_validate_url_accepts_real_substack() -> None:
    import log_publish

    assert log_publish.validate_url("https://stackhub.substack.com/p/decision-fatigue").startswith(
        "https://"
    )


def test_publish_blocks_when_ai_tells_unchecked(
    log_publish_module, tmp_project
) -> None:  # noqa: ANN001
    repo = PostRepository()
    repo.append(PostRecord(post_id="20260501-bad", human_edit_completed=True))
    rc = log_publish_module.main(
        ["--post-id", "20260501-bad", "--url", "https://stackhub.substack.com/p/x"]
    )
    assert rc == 1


def test_publish_blocks_when_retention_unchecked(
    log_publish_module, tmp_project
) -> None:  # noqa: ANN001
    repo = PostRepository()
    repo.append(PostRecord(post_id="20260501-bad", ai_tells_check_passed=True))
    rc = log_publish_module.main(
        ["--post-id", "20260501-bad", "--url", "https://stackhub.substack.com/p/x"]
    )
    assert rc == 1


def test_publish_happy_path_moves_draft(log_publish_module, tmp_project) -> None:  # noqa: ANN001
    record = _seed_eligible()
    draft = tmp_project / "drafts" / f"{record.post_id}_v1.md"
    draft.write_text("# draft\nhello\n", encoding="utf-8")

    rc = log_publish_module.main(
        ["--post-id", record.post_id, "--url", "https://stackhub.substack.com/p/x"]
    )
    assert rc == 0

    repo = PostRepository()
    refreshed = repo.get(record.post_id)
    assert refreshed.status is PostStatus.PUBLISHED
    assert refreshed.substack_url == "https://stackhub.substack.com/p/x"
    assert refreshed.published_at

    moved = tmp_project / "published" / f"{record.post_id}_v1.md"
    assert moved.exists()
    assert not draft.exists()
