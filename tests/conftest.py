"""Shared pytest fixtures.

Each test gets an isolated tmp project root so they never touch the real
`data/posts.json` or `drafts/`. We rebind `pipeline.paths` module-level
constants on the fly via monkeypatch.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Create a project skeleton in tmp_path and rebind pipeline.paths to it."""
    for sub in (
        "corpus",
        "voice",
        "prompts",
        "libraries",
        "briefs",
        "drafts",
        "drafts/calibration",
        "published",
        "data",
        "rituals",
        "rituals/audits",
        "growth",
    ):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)

    # Seed minimum content so prompt rendering works.
    (tmp_path / "voice" / "voice_map.md").write_text(
        "# Voice Map\n\n## Brand Voice Synthesis\nSample synthesis paragraph.\n\n"
        "## Anti-Voice\n- Do not use cinematic openings.\n",
        encoding="utf-8",
    )
    (tmp_path / "voice" / "brand_promise.md").write_text(
        "# Brand Promise\n\n## The One-Sentence Promise\nSample promise.\n",
        encoding="utf-8",
    )
    (tmp_path / "voice" / "ai_tells_killlist.md").write_text(
        "# AI Tells\n1. Kill pattern alpha.\n2. Kill pattern beta.\n",
        encoding="utf-8",
    )
    (tmp_path / "prompts" / "master_system_prompt.md").write_text(
        "# Master\nBrand: {{ brand_name }}\nPromise: {{ brand_promise }}\n"
        "Voice: {{ voice_synthesis }}\nAnti: {{ anti_voice }}\n"
        "Kills: {{ kill_list }}\nRotation: {{ rotation_context }}\n",
        encoding="utf-8",
    )
    (tmp_path / "prompts" / "ai_tells_detector_prompt.md").write_text(
        "Kill list:\n{{ kill_list }}\n\nDraft:\n{{ draft_text }}\n",
        encoding="utf-8",
    )
    (tmp_path / "libraries" / "hook_library.md").write_text("# Hooks\n", encoding="utf-8")
    (tmp_path / "libraries" / "structure_library.md").write_text(
        "# Structures\n", encoding="utf-8"
    )
    (tmp_path / "briefs" / "_TEMPLATE.md").write_text(
        "# Brief\n\n## One Big Idea\n\n## Why this why now\n\n## Target hook pattern\n\n"
        "## Target structural framework\n\n## Rotation Check\n\n"
        "## Reader Transformation\n\n## Forbidden Moves\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "config.json").write_text(
        '{"cadence_days": 7, "brand_name": "Test Brand"}\n', encoding="utf-8"
    )
    (tmp_path / "data" / "posts.json").write_text("[]\n", encoding="utf-8")

    monkeypatch.setenv("STACK_HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    # Disable auth in tests by default. Auth-specific tests can flip this.
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("NOVITA_API_KEY", raising=False)

    # Reload paths + config so STACK_HUB_ROOT takes effect everywhere.
    # (Other modules access paths via `pipeline.paths.X` lazily.)
    import pipeline.paths
    importlib.reload(pipeline.paths)
    import pipeline.config
    importlib.reload(pipeline.config)
    pipeline.config.reset_settings_cache()

    yield tmp_path

    pipeline.config.reset_settings_cache()


@pytest.fixture
def fake_provider() -> object:
    """A stub LLMProvider that returns a fixed response — for unit tests."""
    from pipeline.llm.base import GenerationRequest, LLMProvider

    class _FakeProvider(LLMProvider):
        name = "fake"
        last_request: GenerationRequest | None = None
        canned_response: str = "fake-response"

        def __init__(self) -> None:  # bypass key check
            self._api_key = "fake"
            self._model = "fake-model"

        def _generate(self, request: GenerationRequest) -> str:
            type(self).last_request = request
            return type(self).canned_response

    return _FakeProvider()
