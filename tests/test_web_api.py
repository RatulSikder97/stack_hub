"""FastAPI endpoint tests using TestClient with a stubbed provider."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from pipeline.config import Settings
from pipeline.llm.base import GenerationRequest, LLMProvider


class _ScriptedProvider(LLMProvider):
    """Returns canned responses in order. Reusable across every endpoint."""

    name = "scripted"

    def __init__(self, responses: list[str]) -> None:
        self._api_key = "stub"
        self._model = "stub-model"
        self._responses = list(responses)
        self.calls: list[GenerationRequest] = []

    def _generate(self, request: GenerationRequest) -> str:
        self.calls.append(request)
        if not self._responses:
            return "{}"
        return self._responses.pop(0)


@pytest.fixture
def make_app(tmp_project, monkeypatch):  # noqa: ANN001
    """Return a function that builds an app with a scripted provider."""
    from pipeline.web import create_app

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from pipeline.config import reset_settings_cache

    reset_settings_cache()

    def _factory(responses: list[str]) -> tuple[TestClient, _ScriptedProvider]:
        provider = _ScriptedProvider(responses)

        def _build(_settings: Settings) -> LLMProvider:
            return provider

        app = create_app(provider_factory=_build)
        return TestClient(app), provider

    return _factory


# --- Status / index --------------------------------------------------------


def test_status_endpoint(make_app) -> None:  # noqa: ANN001
    client, _ = make_app([])
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "openai"
    assert data["has_active_provider_key"] is True
    assert data["brand_name"] == "Test Brand"


def test_index_renders_html(make_app) -> None:  # noqa: ANN001
    client, _ = make_app([])
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    # When the React SPA build is present, "/" returns the SPA shell; the
    # legacy template-based panel includes the brand name. Either is valid.
    assert "Test Brand" in res.text or "Stack Hub" in res.text


# --- Translate -------------------------------------------------------------


def test_translate_bengali_to_english(make_app) -> None:  # noqa: ANN001
    payload = json.dumps(
        {"source_language": "bn", "translated_text": "Default decisions matter."}
    )
    client, _ = make_app([payload])
    res = client.post(
        "/api/translate", json={"text": "ডিফল্ট সিদ্ধান্ত", "target_lang": "en"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["translated_text"] == "Default decisions matter."
    assert body["source_language"] == "bn"
    assert body["needed_translation"] is True


def test_translate_empty_returns_400(make_app) -> None:  # noqa: ANN001
    client, _ = make_app([])
    res = client.post("/api/translate", json={"text": "   "})
    assert res.status_code == 400


# --- Brief -----------------------------------------------------------------


def _brief_responses() -> list[str]:
    translation = json.dumps(
        {"source_language": "bn", "translated_text": "Default decisions beat discipline."}
    )
    brief = json.dumps(
        {
            "working_title": "Default Decisions Beat Willpower",
            "one_big_idea": "Most willpower failures are default-design failures.",
            "why_now": "Knowledge workers are exhausted mid-year.",
            "target_hook": "Counterintuitive Open",
            "target_framework": "The Concept Lens",
            "reader_transformation": "Reader picks one default to redesign this week.",
            "forbidden_moves": ["No willpower-as-muscle metaphor."],
        }
    )
    return [translation, brief]


def test_brief_endpoint_creates_brief_and_record(
    make_app, tmp_project
) -> None:  # noqa: ANN001
    client, _ = make_app(_brief_responses())
    res = client.post(
        "/api/brief", json={"idea": "ডিফল্ট সিদ্ধান্ত", "target_lang": "en"}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["working_title"] == "Default Decisions Beat Willpower"
    assert body["target_hook"] == "Counterintuitive Open"
    assert body["needed_translation"] is True
    assert body["source_language"] == "bn"

    brief_path = tmp_project / "briefs" / f"{body['post_id']}.md"
    assert brief_path.exists()
    text = brief_path.read_text(encoding="utf-8")
    assert "## Source Idea" in text

    posts = client.get("/api/posts").json()["posts"]
    assert len(posts) == 1
    assert posts[0]["working_title"] == "Default Decisions Beat Willpower"


def test_brief_empty_idea_returns_400(make_app) -> None:  # noqa: ANN001
    client, _ = make_app([])
    res = client.post("/api/brief", json={"idea": "   "})
    assert res.status_code == 400


# --- Draft -----------------------------------------------------------------


def test_draft_endpoint(make_app, tmp_project) -> None:  # noqa: ANN001
    # Two responses for brief composition + one for draft generation.
    draft_text = "# Title\n\nThis is a generated draft body.\n"
    client, _ = make_app([*_brief_responses(), draft_text])

    brief = client.post("/api/brief", json={"idea": "test idea"}).json()
    post_id = brief["post_id"]

    res = client.post(f"/api/draft/{post_id}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["text"].startswith("# Title")
    assert body["word_count"] >= 1

    draft_file = tmp_project / "drafts" / f"{post_id}_v1.md"
    assert draft_file.exists()


def test_draft_unknown_post_id_returns_404(make_app) -> None:  # noqa: ANN001
    client, _ = make_app([])
    res = client.post("/api/draft/missing-id")
    assert res.status_code == 404


# --- Detect ----------------------------------------------------------------


def test_detect_endpoint_uses_local_when_dirty(
    make_app, tmp_project
) -> None:  # noqa: ANN001
    """Even with a provider key, a draft full of obvious tells should yield flags."""
    dirty_draft = (
        "It's not just hard, it's nearly impossible.\n\n"
        "Let's dive into the model — quickly, deeply, fully.\n\n"
        "The choice is yours.\n"
    )
    judge_payload = json.dumps(
        {
            "flags": [
                {
                    "pattern": "its_not_just_x_its_y",
                    "snippet": "It's not just hard, it's nearly impossible.",
                    "line_approx": 1,
                }
            ],
            "passed": False,
        }
    )
    client, _ = make_app([*_brief_responses(), dirty_draft, judge_payload])
    brief = client.post("/api/brief", json={"idea": "x"}).json()
    post_id = brief["post_id"]
    client.post(f"/api/draft/{post_id}").raise_for_status()

    res = client.post(f"/api/detect/{post_id}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["passed"] is False
    assert len(body["flags"]) >= 1


# --- Publish ---------------------------------------------------------------


def test_publish_blocked_when_gates_unmet(make_app) -> None:  # noqa: ANN001
    client, _ = make_app(_brief_responses())
    brief = client.post("/api/brief", json={"idea": "x"}).json()
    res = client.post(
        f"/api/publish/{brief['post_id']}",
        json={"url": "https://stackhub.substack.com/p/x"},
    )
    assert res.status_code == 400
    assert "ai_tells_check_passed" in res.json()["detail"]


def test_publish_rejects_example_url(make_app, tmp_project) -> None:  # noqa: ANN001
    """Even with both gates passed, example.com URLs must be refused."""
    clean_draft = "A clean paragraph.\n\nA second paragraph.\n\nA closing thought.\n"
    client, _ = make_app([*_brief_responses(), clean_draft])
    brief = client.post("/api/brief", json={"idea": "x"}).json()
    post_id = brief["post_id"]
    client.post(f"/api/draft/{post_id}")
    # Use the LOCAL detector path to pass without a judge JSON response.
    # Forcing this requires zero remaining responses for the detector call.
    res = client.post(f"/api/detect/{post_id}")
    assert res.status_code == 200
    client.post(f"/api/retention/{post_id}")
    res = client.post(
        f"/api/publish/{post_id}",
        json={"url": "https://example.substack.com/p/x"},
    )
    assert res.status_code == 400


def test_publish_happy_path(make_app, tmp_project) -> None:  # noqa: ANN001
    clean_draft = "A clean paragraph.\n\nA second paragraph.\n\nA closing thought.\n"
    pass_payload = json.dumps({"flags": [], "passed": True})
    client, _ = make_app([*_brief_responses(), clean_draft, pass_payload])
    brief = client.post("/api/brief", json={"idea": "x"}).json()
    post_id = brief["post_id"]
    client.post(f"/api/draft/{post_id}").raise_for_status()
    client.post(f"/api/detect/{post_id}").raise_for_status()
    client.post(f"/api/retention/{post_id}").raise_for_status()
    res = client.post(
        f"/api/publish/{post_id}",
        json={"url": "https://stackhub.substack.com/p/decision-fatigue"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["substack_url"].endswith("decision-fatigue")
    moved = tmp_project / "published" / f"{post_id}_v1.md"
    assert moved.exists()
