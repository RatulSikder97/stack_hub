"""Recall.ai client + endpoint tests using mocked httpx."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pipeline import recall as recall_module
from pipeline.recall import (
    RecallClient,
    RecallError,
    RecallNotConfigured,
    _build_provider_options,
    _format_transcript,
    _simplify_state,
)


# ---- Status simplification ----


def test_simplify_state_progresses_through_phases() -> None:
    assert _simplify_state([]) == "queued"
    assert _simplify_state(["ready"]) == "queued"
    assert _simplify_state(["ready", "joining_call"]) == "joining"
    assert _simplify_state(["joining_call", "in_call_recording"]) == "in_call"
    assert _simplify_state(["recording_done", "done"]) == "done"
    assert _simplify_state(["fatal"]) == "error"


def test_simplify_state_uses_latest_known() -> None:
    # Unknown trailing codes are skipped; we keep the latest *known* state.
    assert _simplify_state(["in_call_recording", "weird_unknown_code"]) == "in_call"


def test_simplify_state_call_ended_is_transient_not_done() -> None:
    # call_ended fires when the bot leaves the call but BEFORE Recall has
    # finalized the transcript. Treating it as terminal stops polling early
    # and fetches an empty transcript. State must remain "in_call" until
    # recording_done/done arrives.
    assert _simplify_state(["in_call_recording", "call_ended"]) == "in_call"
    assert _simplify_state(["in_call_recording", "call_ended", "recording_done"]) == "done"
    assert _simplify_state(["in_call_recording", "call_ended", "recording_done", "done"]) == "done"


# ---- Transcript formatting ----


def test_format_transcript_inline_speaker_text() -> None:
    payload = [
        {"speaker": "Alice", "text": "Hello."},
        {"speaker": "Alice", "text": "How are you?"},
        {"speaker": "Bob", "text": "Fine."},
    ]
    formatted = _format_transcript(payload)
    assert formatted == "Alice: Hello. How are you?\nBob: Fine."


def test_format_transcript_words_array() -> None:
    payload = {
        "data": [
            {
                "speaker": {"name": "Alice"},
                "words": [{"text": "Hello"}, {"text": "world."}],
            }
        ]
    }
    assert _format_transcript(payload) == "Alice: Hello world."


def test_format_transcript_recall_diarized_shape() -> None:
    # Recall's current S3 transcript format: list of utterances with
    # `participant: {name}` (not `speaker`) and a `words[]` array.
    payload = [
        {
            "participant": {"name": "Ratul Sikder", "is_host": True},
            "words": [{"text": "Hi"}, {"text": "everyone."}],
            "language_code": "en",
        },
        {
            "participant": {"name": "Other"},
            "words": [{"text": "Hello."}],
            "language_code": "en",
        },
    ]
    assert _format_transcript(payload) == "Ratul Sikder: Hi everyone.\nOther: Hello."


def test_format_transcript_plain_string() -> None:
    assert _format_transcript("Plain string transcript.") == "Plain string transcript."


def test_format_transcript_empty() -> None:
    assert _format_transcript([]) == ""
    assert _format_transcript({}) == ""


# ---- Client lifecycle ----


def test_recall_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RECALL_API_KEY", raising=False)
    with pytest.raises(RecallNotConfigured):
        RecallClient()


class _FakeHttpClient:
    """Mock the subset of httpx.Client we use."""

    def __init__(self, scripted: dict[tuple[str, str], object]) -> None:
        self.scripted = scripted
        self.calls: list[tuple[str, str, dict | None]] = []

    def request(self, method: str, url: str, json=None, headers=None):  # noqa: ANN001
        self.calls.append((method, url, json))
        path = url.split("recall.ai")[-1]
        key = (method, path)
        result = self.scripted.get(key)
        if result is None:
            raise AssertionError(f"unexpected request {method} {path}")
        return _FakeResponse(*result)

    def close(self) -> None:
        pass


class _FakeResponse:
    def __init__(self, status_code: int, body: object) -> None:
        self.status_code = status_code
        self._body = body
        self.text = str(body) if body is not None else ""
        self.content = self.text.encode("utf-8") if self.text else b""

    def json(self) -> object:
        if isinstance(self._body, (dict, list)):
            return self._body
        raise ValueError("not json")


def test_create_bot_returns_id(monkeypatch: pytest.MonkeyPatch) -> None:
    # Clear env so we test the hard-coded default, not whatever the host has set.
    for var in ("RECALL_TRANSCRIPTION_PROVIDER", "RECALL_TRANSCRIPTION_LANGUAGE", "RECALL_TRANSCRIPTION_MODEL"):
        monkeypatch.delenv(var, raising=False)
    fake = _FakeHttpClient(
        {
            ("POST", "/api/v1/bot/"): (
                201,
                {"id": "bot-uuid-123", "status_changes": [{"code": "ready"}]},
            )
        }
    )
    client = RecallClient(api_key="test", client=fake)
    bot_id = client.create_bot("https://zoom.us/j/123")
    assert bot_id == "bot-uuid-123"
    method, path, body = fake.calls[0]
    assert method == "POST"
    assert "/bot/" in path
    assert body["meeting_url"] == "https://zoom.us/j/123"
    assert body["recording_config"]["transcript"]["provider"] == {"meeting_captions": {}}
    assert "transcription_options" not in body


def test_create_bot_uses_env_provider_language_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECALL_TRANSCRIPTION_PROVIDER", "deepgram_streaming")
    monkeypatch.setenv("RECALL_TRANSCRIPTION_LANGUAGE", "bn")
    monkeypatch.setenv("RECALL_TRANSCRIPTION_MODEL", "nova-2-general")
    fake = _FakeHttpClient(
        {("POST", "/api/v1/bot/"): (201, {"id": "bot-2", "status_changes": []})}
    )
    client = RecallClient(api_key="test", client=fake)
    client.create_bot("https://zoom.us/j/x")
    body = fake.calls[0][2]
    assert body["recording_config"]["transcript"]["provider"] == {
        "deepgram_streaming": {"language": "bn", "model": "nova-2-general"}
    }


def test_create_bot_kwargs_override_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECALL_TRANSCRIPTION_PROVIDER", "deepgram_streaming")
    monkeypatch.setenv("RECALL_TRANSCRIPTION_LANGUAGE", "bn")
    fake = _FakeHttpClient(
        {("POST", "/api/v1/bot/"): (201, {"id": "bot-3", "status_changes": []})}
    )
    client = RecallClient(api_key="test", client=fake)
    client.create_bot(
        "https://zoom.us/j/x",
        transcription_provider="meeting_captions",
        transcription_language="",
    )
    body = fake.calls[0][2]
    assert body["recording_config"]["transcript"]["provider"] == {"meeting_captions": {}}


def test_build_provider_options_meeting_captions_ignores_other_args() -> None:
    assert _build_provider_options("meeting_captions", "bn", "nova-2") == {}


def test_build_provider_options_deepgram_omits_empty_fields() -> None:
    assert _build_provider_options("deepgram_streaming", "", "") == {}
    assert _build_provider_options("deepgram_streaming", "bn", "") == {"language": "bn"}
    assert _build_provider_options("deepgram_streaming", "bn", "nova-2") == {
        "language": "bn",
        "model": "nova-2",
    }


def test_get_status_done_pulls_transcript() -> None:
    s3_url = "https://example-bucket.s3.amazonaws.com/transcript.json?X-Sig=abc"
    fake = _FakeHttpClient(
        {
            ("GET", "/api/v1/bot/bot-1/"): (
                200,
                {
                    "id": "bot-1",
                    "status_changes": [
                        {"code": "ready"},
                        {"code": "joining_call"},
                        {"code": "in_call_recording"},
                        {"code": "call_ended"},
                        {"code": "recording_done"},
                        {"code": "done"},
                    ],
                    "recordings": [
                        {
                            "media_shortcuts": {
                                "transcript": {
                                    "data": {"download_url": s3_url},
                                },
                            },
                        }
                    ],
                },
            ),
            ("GET", s3_url): (
                200,
                [
                    {"participant": {"name": "Alice"}, "words": [{"text": "Welcome."}]},
                    {"participant": {"name": "Bob"}, "words": [{"text": "Thanks."}]},
                ],
            ),
        }
    )
    client = RecallClient(api_key="test", client=fake)
    status = client.get_status("bot-1")
    assert status.state == "done"
    assert status.transcript_text == "Alice: Welcome.\nBob: Thanks."
    assert status.error is None


def test_get_status_in_progress_returns_no_transcript() -> None:
    fake = _FakeHttpClient(
        {
            ("GET", "/api/v1/bot/bot-1/"): (
                200,
                {"id": "bot-1", "status_changes": [{"code": "in_call_recording"}]},
            )
        }
    )
    client = RecallClient(api_key="test", client=fake)
    status = client.get_status("bot-1")
    assert status.state == "in_call"
    assert status.transcript_text is None


def test_get_status_fatal_surfaces_message() -> None:
    fake = _FakeHttpClient(
        {
            ("GET", "/api/v1/bot/bot-1/"): (
                200,
                {
                    "id": "bot-1",
                    "status_changes": [
                        {"code": "ready"},
                        {"code": "fatal", "message": "Could not join meeting"},
                    ],
                },
            )
        }
    )
    client = RecallClient(api_key="test", client=fake)
    status = client.get_status("bot-1")
    assert status.state == "error"
    assert status.error == "Could not join meeting"


def test_create_bot_http_error_wrapped() -> None:
    fake = _FakeHttpClient({("POST", "/api/v1/bot/"): (400, {"detail": "bad url"})})
    client = RecallClient(api_key="test", client=fake)
    with pytest.raises(RecallError):
        client.create_bot("not-a-url")


# ---- API endpoint integration ----


@pytest.fixture
def client_with_recall(tmp_project, monkeypatch):  # noqa: ANN001
    """Patch RecallClient to a deterministic stub for endpoint tests."""
    from fastapi.testclient import TestClient as _TestClient

    from pipeline.web import create_app

    monkeypatch.setenv("RECALL_API_KEY", "test-key")
    monkeypatch.setenv("AUTH_DISABLED", "true")

    fake_calls: dict[str, object] = {}

    class _FakeRecall:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN001
            pass

        def create_bot(self, url: str, *, bot_name: str = "Stack Hub", **_: object) -> str:
            fake_calls["created"] = url
            return "bot-stub-001"

        def get_status(self, bot_id: str):  # noqa: ANN001
            from pipeline.recall import RecallBotStatus

            return RecallBotStatus(
                bot_id=bot_id,
                state="done",
                raw_status_codes=["ready", "in_call_recording", "recording_done"],
                transcript_text="Alice: Hello world.",
                error=None,
            )

        def leave_call(self, bot_id: str) -> None:
            fake_calls["left"] = bot_id

    monkeypatch.setattr(recall_module, "RecallClient", _FakeRecall)
    # Also patch the import inside the api module.
    from pipeline.web import api as web_api

    monkeypatch.setattr(web_api, "RecallClient", _FakeRecall)
    return _TestClient(create_app()), fake_calls


def test_create_bot_endpoint_returns_id(client_with_recall) -> None:  # noqa: ANN001
    client, calls = client_with_recall
    res = client.post("/api/meeting/bot", json={"meeting_url": "https://zoom.us/j/x"})
    assert res.status_code == 200
    assert res.json() == {"bot_id": "bot-stub-001"}
    assert calls["created"] == "https://zoom.us/j/x"


def test_create_bot_rejects_empty_url(client_with_recall) -> None:  # noqa: ANN001
    client, _ = client_with_recall
    res = client.post("/api/meeting/bot", json={"meeting_url": ""})
    assert res.status_code == 400


def test_get_bot_status_returns_transcript(client_with_recall) -> None:  # noqa: ANN001
    client, _ = client_with_recall
    res = client.get("/api/meeting/bot/bot-stub-001")
    assert res.status_code == 200
    body = res.json()
    assert body["state"] == "done"
    assert body["transcript_text"] == "Alice: Hello world."


def test_leave_bot_endpoint(client_with_recall) -> None:  # noqa: ANN001
    client, calls = client_with_recall
    res = client.delete("/api/meeting/bot/bot-stub-001")
    assert res.status_code == 200
    assert res.json() == {"bot_id": "bot-stub-001", "left": True}
    assert calls["left"] == "bot-stub-001"


def test_endpoint_returns_503_when_recall_not_configured(
    tmp_project, monkeypatch
) -> None:  # noqa: ANN001
    """If RECALL_API_KEY is missing, dispatch returns 503 with a clear hint."""
    from pipeline.web import create_app

    monkeypatch.delenv("RECALL_API_KEY", raising=False)
    monkeypatch.setenv("AUTH_DISABLED", "true")
    client = TestClient(create_app())
    res = client.post("/api/meeting/bot", json={"meeting_url": "https://zoom.us/j/x"})
    assert res.status_code == 503
    assert "RECALL_API_KEY" in res.json()["detail"]
