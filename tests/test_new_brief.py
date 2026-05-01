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


def test_from_idea_path_invokes_composer(
    new_brief_module, tmp_project, monkeypatch
) -> None:  # noqa: ANN001
    """`--from-idea` should call IdeaToBrief and write a populated brief."""
    import json as _json

    from pipeline.brief_builder import BriefDraft
    from pipeline.translation import TranslationResult

    fake_translation = TranslationResult(
        original_text="ডিফল্ট সিদ্ধান্ত",
        translated_text="Default decisions",
        source_language="bn",
        target_language="en",
        needed_translation=True,
    )
    fake_draft = BriefDraft(
        working_title="Default Decisions Beat Willpower",
        one_big_idea="Most willpower failures are default-design failures.",
        why_now="Mid-year energy is running out.",
        target_hook="Counterintuitive Open",
        target_framework="The Concept Lens",
        reader_transformation="Reader converts one daily re-decision into a default.",
        forbidden_moves=["No willpower-as-muscle metaphor."],
        translation=fake_translation,
    )

    class _FakeComposer:
        def __init__(self, *_args, **_kwargs) -> None:  # noqa: ANN001
            pass

        def build(self, idea: str, *, target_language: str = "en") -> BriefDraft:
            assert idea.strip()
            assert target_language == "en"
            return fake_draft

    class _FakeProvider:
        pass

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from pipeline.config import reset_settings_cache

    reset_settings_cache()
    monkeypatch.setattr(new_brief_module, "build_provider", lambda *_a, **_k: _FakeProvider())
    monkeypatch.setattr(new_brief_module, "IdeaToBrief", _FakeComposer)

    rc = new_brief_module.main(["--from-idea", "ডিফল্ট সিদ্ধান্ত"])
    assert rc == 0

    repo = PostRepository()
    posts = repo.list()
    assert len(posts) == 1
    assert posts[0].working_title == "Default Decisions Beat Willpower"
    assert posts[0].hook_pattern_used == "Counterintuitive Open"
    assert posts[0].structural_framework_used == "The Concept Lens"

    brief_body = (tmp_project / "briefs" / f"{posts[0].post_id}.md").read_text(encoding="utf-8")
    assert "## Source Idea" in brief_body
    assert "ডিফল্ট সিদ্ধান্ত" in brief_body
    assert "Default decisions" in brief_body
    _ = _json  # silence unused import lint


def test_from_idea_requires_provider_key(
    new_brief_module, tmp_project, monkeypatch
) -> None:  # noqa: ANN001
    """Without an API key the --from-idea path must fail with rc=2."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from pipeline.config import reset_settings_cache

    reset_settings_cache()
    rc = new_brief_module.main(["--from-idea", "anything"])
    assert rc == 2


def test_title_and_from_idea_are_mutually_exclusive(new_brief_module, tmp_project) -> None:  # noqa: ANN001
    with pytest.raises(SystemExit):
        new_brief_module.main(["--title", "x", "--from-idea", "y"])


def test_from_idea_file_reads_from_disk(
    new_brief_module, tmp_project, monkeypatch
) -> None:  # noqa: ANN001
    """`--from-idea-file` must load the file and pass it to the composer."""
    from pipeline.brief_builder import BriefDraft
    from pipeline.translation import TranslationResult

    idea_file = tmp_project / "idea.md"
    idea_file.write_text("ডিফল্ট সিদ্ধান্ত গুরুত্বপূর্ণ", encoding="utf-8")

    fake_draft = BriefDraft(
        working_title="From File Title",
        one_big_idea="One.",
        why_now="Why.",
        target_hook="Confession",
        target_framework="The Reversal",
        reader_transformation="Reader.",
        forbidden_moves=["No clichés."],
        translation=TranslationResult(
            original_text="ডিফল্ট",
            translated_text="Defaults",
            source_language="bn",
            target_language="en",
            needed_translation=True,
        ),
    )

    captured: dict[str, str] = {}

    class _FakeComposer:
        def __init__(self, *_a, **_k) -> None:  # noqa: ANN001
            pass

        def build(self, idea: str, *, target_language: str = "en") -> BriefDraft:
            captured["idea"] = idea
            return fake_draft

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from pipeline.config import reset_settings_cache

    reset_settings_cache()
    monkeypatch.setattr(new_brief_module, "build_provider", lambda *_a, **_k: object())
    monkeypatch.setattr(new_brief_module, "IdeaToBrief", _FakeComposer)

    rc = new_brief_module.main(["--from-idea-file", str(idea_file)])
    assert rc == 0
    assert "ডিফল্ট সিদ্ধান্ত গুরুত্বপূর্ণ" in captured["idea"]


def test_from_idea_stdin_dash(
    new_brief_module, tmp_project, monkeypatch
) -> None:  # noqa: ANN001
    """`--from-idea -` should read from stdin."""
    import io

    from pipeline.brief_builder import BriefDraft
    from pipeline.translation import TranslationResult

    fake_draft = BriefDraft(
        working_title="Stdin Title",
        one_big_idea="One.",
        why_now="Why.",
        target_hook="Confession",
        target_framework="The Reversal",
        reader_transformation="Reader.",
        forbidden_moves=["No clichés."],
        translation=TranslationResult(
            original_text="ডিফল্ট",
            translated_text="Defaults",
            source_language="bn",
            target_language="en",
            needed_translation=True,
        ),
    )

    captured: dict[str, str] = {}

    class _FakeComposer:
        def __init__(self, *_a, **_k) -> None:  # noqa: ANN001
            pass

        def build(self, idea: str, *, target_language: str = "en") -> BriefDraft:
            captured["idea"] = idea
            return fake_draft

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from pipeline.config import reset_settings_cache

    reset_settings_cache()
    monkeypatch.setattr(new_brief_module, "build_provider", lambda *_a, **_k: object())
    monkeypatch.setattr(new_brief_module, "IdeaToBrief", _FakeComposer)
    monkeypatch.setattr("sys.stdin", io.StringIO("পাইপ থেকে ধারণা"))

    rc = new_brief_module.main(["--from-idea", "-"])
    assert rc == 0
    assert captured["idea"].strip() == "পাইপ থেকে ধারণা"
