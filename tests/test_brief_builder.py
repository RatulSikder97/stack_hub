"""IdeaToBrief composer."""

from __future__ import annotations

import json

import pytest

from pipeline.brief_builder import BriefBuildError, IdeaToBrief
from pipeline.llm.base import GenerationRequest, LLMProvider


class _ScriptedProvider(LLMProvider):
    """Returns responses in the order they are queued."""

    name = "scripted"

    def __init__(self, responses: list[str]) -> None:
        self._api_key = "stub"
        self._model = "stub-model"
        self._responses = list(responses)
        self.calls: list[GenerationRequest] = []

    def _generate(self, request: GenerationRequest) -> str:
        self.calls.append(request)
        if not self._responses:
            raise RuntimeError("No more scripted responses")
        return self._responses.pop(0)


@pytest.fixture
def translation_payload() -> str:
    return json.dumps(
        {"source_language": "bn", "translated_text": "Default decisions beat discipline."}
    )


@pytest.fixture
def brief_payload() -> str:
    return json.dumps(
        {
            "working_title": "Default Decisions Beat Willpower",
            "one_big_idea": "Most willpower failures are default-design failures.",
            "why_now": "Knowledge workers are running out of discretionary energy mid-year.",
            "target_hook": "Counterintuitive Open",
            "target_framework": "The Concept Lens",
            "reader_transformation": "Reader audits one decision they re-make daily and converts it to a default.",
            "forbidden_moves": [
                "No willpower-as-muscle metaphor.",
                "No three-step productivity framework.",
                "Do not lecture about discipline.",
            ],
        }
    )


def test_build_from_bengali(
    tmp_project, translation_payload, brief_payload
) -> None:  # noqa: ANN001
    provider = _ScriptedProvider([translation_payload, brief_payload])
    composer = IdeaToBrief(provider=provider)
    draft = composer.build("ডিফল্ট সিদ্ধান্ত ইচ্ছাশক্তির চেয়ে বেশি গুরুত্বপূর্ণ")

    assert draft.working_title == "Default Decisions Beat Willpower"
    assert draft.target_hook == "Counterintuitive Open"
    assert draft.target_framework == "The Concept Lens"
    assert len(draft.forbidden_moves) == 3
    assert draft.translation is not None
    assert draft.translation.source_language == "bn"
    assert draft.translation.needed_translation is True


def test_render_includes_source_idea_section(
    tmp_project, translation_payload, brief_payload
) -> None:  # noqa: ANN001
    provider = _ScriptedProvider([translation_payload, brief_payload])
    draft = IdeaToBrief(provider=provider).build("ডিফল্ট")
    rendered = draft.render()
    assert "## Working Title" in rendered
    assert "## One Big Idea" in rendered
    assert "## Source Idea" in rendered
    assert "Default Decisions Beat Willpower" in rendered


def test_invalid_brief_json_raises(tmp_project, translation_payload) -> None:  # noqa: ANN001
    provider = _ScriptedProvider([translation_payload, "not json"])
    composer = IdeaToBrief(provider=provider)
    with pytest.raises(BriefBuildError):
        composer.build("ডিফল্ট")


def test_empty_idea_rejected(tmp_project) -> None:  # noqa: ANN001
    provider = _ScriptedProvider([])
    with pytest.raises(ValueError, match="empty"):
        IdeaToBrief(provider=provider).build("   ")
