"""draft_post CLI behavior — exercised in --mock mode (no API call)."""

from __future__ import annotations

import importlib

import pytest

from pipeline.models import PostRecord, PostStatus
from pipeline.repository import PostRepository


@pytest.fixture
def draft_post_module(tmp_project):  # noqa: ANN001
    import draft_post
    return importlib.reload(draft_post)


def test_mock_draft_writes_file_and_updates_status(
    draft_post_module, tmp_project
) -> None:  # noqa: ANN001
    repo = PostRepository()
    post = PostRecord(post_id="20260501-x", working_title="X", status=PostStatus.BRIEF)
    repo.append(post)
    (tmp_project / "briefs" / "20260501-x.md").write_text("# brief", encoding="utf-8")

    rc = draft_post_module.main(["--post-id", "20260501-x", "--mock"])
    assert rc == 0

    out = tmp_project / "drafts" / "20260501-x_v1.md"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# 20260501-x")
    assert "MOCK_DRAFT" in text

    refreshed = repo.get("20260501-x")
    assert refreshed.status is PostStatus.DRAFTING


def test_missing_post_id_returns_2(draft_post_module, tmp_project) -> None:  # noqa: ANN001
    rc = draft_post_module.main(["--post-id", "ghost", "--mock"])
    assert rc == 2


def test_uses_provider_when_key_present(
    draft_post_module, tmp_project, monkeypatch
) -> None:  # noqa: ANN001
    repo = PostRepository()
    repo.append(PostRecord(post_id="20260501-y", working_title="Y", status=PostStatus.BRIEF))
    (tmp_project / "briefs" / "20260501-y.md").write_text("# y", encoding="utf-8")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    from pipeline.config import reset_settings_cache

    reset_settings_cache()

    captured = {}

    class _StubProvider:
        model = "stub-model"

        def generate(self, system, user, **kwargs):  # noqa: ANN001
            captured["system"] = system
            captured["user"] = user
            return "# generated draft\nbody"

    monkeypatch.setattr(draft_post_module, "build_provider", lambda *_a, **_k: _StubProvider())

    rc = draft_post_module.main(["--post-id", "20260501-y"])
    assert rc == 0
    out = (tmp_project / "drafts" / "20260501-y_v1.md").read_text(encoding="utf-8")
    assert "generated draft" in out
    assert "Brand: Test Brand" in captured["system"]
    assert "## BRIEF" in captured["user"]
