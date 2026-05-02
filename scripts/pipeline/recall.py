"""Thin wrapper over the Recall.ai bot API.

Recall.ai is a bot-as-a-service for joining Zoom / Google Meet / Teams calls
and producing transcripts. We use it for the "real-time meeting" path of the
pipeline: paste a meeting URL, the bot joins, we poll until it leaves, then
hand the transcript to the brief composer.

This module hides the details of their REST API behind a small typed
surface so the rest of the codebase doesn't care which version we're on.

* ``create_bot(meeting_url)`` → ``bot_id``
* ``get_status(bot_id)``       → ``RecallBotStatus``
* ``leave_call(bot_id)``       → fire-and-forget

Pricing reminder: Recall charges per bot-minute. Default config keeps the
bot in the meeting until it ends OR until ``leave_call`` is invoked.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from dotenv import load_dotenv

# Make sure RECALL_API_KEY is visible from .env even when launched without
# a process-wide env loader.
try:
    from pipeline.paths import ENV_PATH as _ENV_PATH

    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=False)
except Exception:  # noqa: BLE001
    pass


RecallState = Literal["queued", "joining", "in_call", "done", "error"]
DEFAULT_BASE_URL = "https://us-east-1.recall.ai/api/v1"


class RecallError(RuntimeError):
    """Generic Recall.ai failure (HTTP, parsing, or bot-state error)."""


class RecallNotConfigured(RecallError):
    """RECALL_API_KEY is missing from the environment."""


@dataclass(frozen=True)
class RecallBotStatus:
    bot_id: str
    state: RecallState
    raw_status_codes: list[str]
    transcript_text: str | None
    error: str | None


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------

# Recall.ai emits a sequence of status_changes. We collapse them into one of
# five simplified states the rest of the app cares about.
_STATE_MAP: dict[str, RecallState] = {
    "ready": "queued",
    "joining_call": "joining",
    "in_waiting_room": "joining",
    "in_call_not_recording": "in_call",
    "in_call_recording": "in_call",
    "call_ended": "done",
    "recording_done": "done",
    "done": "done",
    "fatal": "error",
}


def _simplify_state(status_codes: list[str]) -> RecallState:
    if not status_codes:
        return "queued"
    # Walk from latest to earliest — the last state with a known mapping wins.
    for code in reversed(status_codes):
        mapped = _STATE_MAP.get(code)
        if mapped is not None:
            return mapped
    return "queued"


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class RecallClient:
    """Synchronous Recall.ai client (httpx).

    Intentionally tiny — only the three calls we need.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        resolved_key = (api_key or os.environ.get("RECALL_API_KEY") or "").strip()
        if not resolved_key:
            raise RecallNotConfigured(
                "RECALL_API_KEY is not set. Add it to .env to enable the meeting bot."
            )
        self._api_key = resolved_key
        self._base_url = (base_url or os.environ.get("RECALL_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout
        self._client = client  # if None, build per-request to keep this stateless

    # ----- public ---------------------------------------------------------

    def create_bot(
        self,
        meeting_url: str,
        *,
        bot_name: str = "Stack Hub",
        transcription_provider: str = "meeting_captions",
    ) -> str:
        """Send a bot to a meeting. Returns the bot_id."""
        if not meeting_url.strip():
            raise RecallError("meeting_url must not be empty")
        body: dict[str, Any] = {
            "meeting_url": meeting_url.strip(),
            "bot_name": bot_name,
            "transcription_options": {"provider": transcription_provider},
        }
        data = self._post("/bot/", body)
        bot_id = str(data.get("id") or "")
        if not bot_id:
            raise RecallError(f"create_bot returned no id: {data!r}")
        return bot_id

    def get_status(self, bot_id: str) -> RecallBotStatus:
        if not bot_id:
            raise RecallError("bot_id required")
        data = self._get(f"/bot/{bot_id}/")
        codes = _extract_status_codes(data)
        state = _simplify_state(codes)
        transcript_text: str | None = None
        error_msg: str | None = None
        if state == "done":
            transcript_text = self._fetch_transcript_text(bot_id, data)
        elif state == "error":
            error_msg = _extract_error(data, codes)
        return RecallBotStatus(
            bot_id=bot_id,
            state=state,
            raw_status_codes=codes,
            transcript_text=transcript_text,
            error=error_msg,
        )

    def leave_call(self, bot_id: str) -> None:
        if not bot_id:
            return
        try:
            self._post(f"/bot/{bot_id}/leave_call/", body=None, allow_404=True)
        except RecallError:
            # leaving a bot that's already gone is fine
            return

    # ----- internals ------------------------------------------------------

    def _fetch_transcript_text(self, bot_id: str, bot_data: dict[str, Any]) -> str | None:
        """Try multiple shapes Recall has used; degrade gracefully."""
        # Newer Recall API: GET /bot/{id}/transcript/?include=words
        try:
            data = self._get(f"/bot/{bot_id}/transcript/")
            return _format_transcript(data)
        except RecallError:
            pass

        # Older shape: bot_data["recordings"][0]["transcript"]
        recordings = bot_data.get("recordings") or []
        for rec in recordings:
            transcript = rec.get("transcript")
            if transcript:
                return _format_transcript(transcript)
        return None

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        allow_404: bool = False,
    ) -> Any:
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Accept": "application/json",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"

        do_close = self._client is None
        client = self._client or httpx.Client(timeout=self._timeout)
        try:
            response = client.request(method, url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise RecallError(f"recall.ai network error: {exc}") from exc
        finally:
            if do_close:
                client.close()

        if response.status_code == 404 and allow_404:
            return None
        if response.status_code >= 400:
            text = response.text[:500]
            raise RecallError(
                f"recall.ai {method} {path} -> {response.status_code}: {text}"
            )
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise RecallError(f"recall.ai response not JSON: {response.text[:200]}") from exc

    def _get(self, path: str) -> Any:
        return self._request("GET", path)

    def _post(self, path: str, body: dict[str, Any] | None, *, allow_404: bool = False) -> Any:
        return self._request("POST", path, body, allow_404=allow_404)


# ---------------------------------------------------------------------------
# Helpers (module-level so tests can call them directly)
# ---------------------------------------------------------------------------


def _extract_status_codes(bot_data: dict[str, Any]) -> list[str]:
    changes = bot_data.get("status_changes") or []
    out: list[str] = []
    for entry in changes:
        if isinstance(entry, dict):
            code = entry.get("code")
            if isinstance(code, str):
                out.append(code)
        elif isinstance(entry, str):
            out.append(entry)
    return out


def _extract_error(bot_data: dict[str, Any], codes: list[str]) -> str:
    changes = bot_data.get("status_changes") or []
    for entry in reversed(changes):
        if isinstance(entry, dict) and entry.get("code") == "fatal":
            msg = entry.get("message")
            if isinstance(msg, str) and msg:
                return msg
    return f"recall.ai bot failed (last codes: {codes[-3:]})" if codes else "recall.ai bot failed"


def _format_transcript(payload: Any) -> str:
    """Convert any Recall transcript shape into ``Speaker: text`` lines."""
    if isinstance(payload, str):
        return payload.strip()

    # Common Recall shape: list of utterances with speaker + words
    if isinstance(payload, list):
        return _format_utterances(payload)

    # Newer shape: {"transcript": [{...}]} or {"data": [...]}
    if isinstance(payload, dict):
        for key in ("transcript", "data", "utterances", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return _format_utterances(value)
            if isinstance(value, str):
                return value.strip()
    return ""


def _format_utterances(items: list[Any]) -> str:
    lines: list[str] = []
    last_speaker: str | None = None
    for entry in items:
        if not isinstance(entry, dict):
            continue
        speaker = (
            entry.get("speaker")
            or entry.get("speaker_name")
            or entry.get("name")
            or ""
        )
        if isinstance(speaker, dict):
            speaker = speaker.get("name") or speaker.get("display_name") or ""
        speaker = (speaker or "").strip()
        text = entry.get("text") or entry.get("content") or ""
        if not text:
            words = entry.get("words")
            if isinstance(words, list):
                text = " ".join(
                    str(w.get("text") or w.get("word") or "")
                    for w in words
                    if isinstance(w, dict)
                ).strip()
        text = (text or "").strip()
        if not text:
            continue
        if speaker and speaker != last_speaker:
            lines.append(f"{speaker}: {text}")
        elif speaker and speaker == last_speaker and lines:
            lines[-1] += " " + text
        else:
            lines.append(text)
        last_speaker = speaker or last_speaker
    return "\n".join(lines).strip()
