"""run_ai_tells CLI behavior."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from pipeline.models import PostRecord, PostStatus
from pipeline.repository import PostRepository


@pytest.fixture
def run_ai_tells_module(tmp_project):  # noqa: ANN001
    import run_ai_tells
    return importlib.reload(run_ai_tells)


def _write_draft(tmp_project: Path, post_id: str, body: str) -> Path:
    out = tmp_project / "drafts" / f"{post_id}_v1.md"
    out.write_text(body, encoding="utf-8")
    return out


def test_clean_draft_passes(run_ai_tells_module, tmp_project) -> None:  # noqa: ANN001
    repo = PostRepository()
    repo.append(PostRecord(post_id="20260501-clean", status=PostStatus.DRAFTING))
    draft = _write_draft(
        tmp_project,
        "20260501-clean",
        "A simple paragraph.\n\nA second paragraph.\n\nA closing thought.\n",
    )
    rc = run_ai_tells_module.main([str(draft), "--mock"])
    assert rc == 0
    refreshed = repo.get("20260501-clean")
    assert refreshed.ai_tells_check_passed is True
    assert refreshed.status is PostStatus.AI_TELLS_PASS


def test_dirty_draft_fails(run_ai_tells_module, tmp_project) -> None:  # noqa: ANN001
    repo = PostRepository()
    repo.append(PostRecord(post_id="20260501-dirty", status=PostStatus.DRAFTING))
    draft = _write_draft(
        tmp_project,
        "20260501-dirty",
        "It's not just hard, it's nearly impossible.\n",
    )
    rc = run_ai_tells_module.main([str(draft), "--mock"])
    assert rc == 1
    refreshed = repo.get("20260501-dirty")
    assert refreshed.ai_tells_check_passed is False
    # Status remains drafting since it failed.
    assert refreshed.status is PostStatus.DRAFTING


def test_failure_after_pass_demotes_status(
    run_ai_tells_module, tmp_project
) -> None:  # noqa: ANN001
    """Re-running a failing detector on a previously passed draft must
    demote status back to drafting so the workflow re-gates publishing."""
    repo = PostRepository()
    repo.append(
        PostRecord(
            post_id="20260501-flip",
            status=PostStatus.AI_TELLS_PASS,
            ai_tells_check_passed=True,
        )
    )
    draft = _write_draft(
        tmp_project,
        "20260501-flip",
        "It's not just hard, it's nearly impossible.\n",
    )
    rc = run_ai_tells_module.main([str(draft), "--mock"])
    assert rc == 1
    refreshed = repo.get("20260501-flip")
    assert refreshed.ai_tells_check_passed is False
    assert refreshed.status is PostStatus.DRAFTING


def test_missing_draft_returns_2(run_ai_tells_module) -> None:  # noqa: ANN001
    rc = run_ai_tells_module.main(["nope.md", "--mock"])
    assert rc == 2


def test_infer_post_id_handles_versioned_filename() -> None:
    import run_ai_tells

    assert run_ai_tells.infer_post_id(Path("20260501-x_v3.md")) == "20260501-x"
    assert run_ai_tells.infer_post_id(Path("plain.md")) is None
