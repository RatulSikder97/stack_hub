"""Meeting transcript parsers.

Zoom and Google Meet both export transcripts in standard subtitle formats:

    * Zoom Cloud Recording → ``.vtt`` (WebVTT)
    * Google Meet → Google Doc (rendered as plain text on copy/paste) or
      ``.txt`` exported from the meeting tab
    * Some recorders use ``.srt`` (SubRip)

This module normalizes any of those into clean dialog text suitable for the
brief composer. Speaker labels are preserved when present so the composer can
distinguish voices.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

TranscriptFormat = Literal["vtt", "srt", "text", "unknown"]

_VTT_HEADER_RE = re.compile(r"^WEBVTT\b", re.MULTILINE)
_SRT_FIRST_BLOCK_RE = re.compile(
    r"^\s*\d+\s*\r?\n\d{2}:\d{2}:\d{2}[,.]\d+\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d+",
)
_VTT_TIMESTAMP_RE = re.compile(
    r"\d{2}:\d{2}:\d{2}\.\d+\s*-->\s*\d{2}:\d{2}:\d{2}\.\d+"
)
_SRT_TIMESTAMP_RE = re.compile(
    r"\d{2}:\d{2}:\d{2},\d+\s*-->\s*\d{2}:\d{2}:\d{2},\d+"
)
_VTT_VOICE_RE = re.compile(r"<v\s+([^>]+?)>", re.IGNORECASE)
_GENERIC_TAG_RE = re.compile(r"</?[^>]+>")
_CUE_NUMBER_RE = re.compile(r"^\d+$")


@dataclass(frozen=True)
class ParsedTranscript:
    text: str
    detected_format: TranscriptFormat
    line_count: int
    word_count: int
    speakers: list[str]


def detect_format(content: str) -> TranscriptFormat:
    """Best-effort format detection from the leading bytes."""
    head = content.lstrip()
    if not head:
        return "unknown"
    if _VTT_HEADER_RE.search(head[:64]):
        return "vtt"
    if _SRT_FIRST_BLOCK_RE.match(head):
        return "srt"
    return "text"


def parse(content: str) -> ParsedTranscript:
    """Auto-detect and normalize. Always returns a result; never raises."""
    fmt = detect_format(content)
    if fmt == "vtt":
        text, speakers = _parse_vtt(content)
    elif fmt == "srt":
        text, speakers = _parse_srt(content)
    else:
        text, speakers = _normalize_plain(content)

    line_count = sum(1 for line in text.splitlines() if line.strip())
    word_count = sum(1 for token in text.split() if token)
    return ParsedTranscript(
        text=text,
        detected_format=fmt,
        line_count=line_count,
        word_count=word_count,
        speakers=speakers,
    )


# ---------- VTT ----------


def _parse_vtt(content: str) -> tuple[str, list[str]]:
    out: list[str] = []
    speakers: list[str] = []
    seen_speakers: set[str] = set()

    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "WEBVTT" or line.upper().startswith("WEBVTT "):
            continue
        if line.startswith("NOTE") or line.startswith("STYLE") or line.startswith("REGION"):
            continue
        if "-->" in line and _VTT_TIMESTAMP_RE.search(line):
            continue
        if _CUE_NUMBER_RE.match(line):
            continue
        # Optional cue identifier (alphanumeric without spaces)
        if not any(c.isspace() for c in line) and "<" not in line and len(out) > 0 and out[-1] == "":
            continue
        # Replace <v Speaker> with "Speaker: "
        match = _VTT_VOICE_RE.search(line)
        if match:
            speaker = match.group(1).strip()
            if speaker and speaker not in seen_speakers:
                seen_speakers.add(speaker)
                speakers.append(speaker)
            line = _VTT_VOICE_RE.sub(f"{speaker}: ", line, count=1)
        # Strip remaining tags (e.g. closing </v>, formatting tags).
        line = _GENERIC_TAG_RE.sub("", line)
        out.append(line.strip())

    return _join_dialog(out), speakers


# ---------- SRT ----------


def _parse_srt(content: str) -> tuple[str, list[str]]:
    out: list[str] = []
    speakers: list[str] = []
    seen_speakers: set[str] = set()

    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if "-->" in line and _SRT_TIMESTAMP_RE.search(line):
            continue
        if _CUE_NUMBER_RE.match(line):
            continue
        cleaned = _GENERIC_TAG_RE.sub("", line).strip()
        # Detect "Speaker Name:" prefixes for speaker tracking.
        speaker_match = re.match(r"^([A-Z][A-Za-z' .-]{1,40}):\s+", cleaned)
        if speaker_match:
            name = speaker_match.group(1).strip()
            if name not in seen_speakers:
                seen_speakers.add(name)
                speakers.append(name)
        out.append(cleaned)

    return _join_dialog(out), speakers


# ---------- Plain text ----------


def _normalize_plain(content: str) -> tuple[str, list[str]]:
    """Plain text + Google Meet copy/paste form.

    Meet's "Copy meeting transcript" output looks like:

        Speaker Name (HH:MM)
        What they said.

        Other Speaker (HH:MM)
        Their reply.

    We collapse that into ``Speaker Name: text`` lines and pull a unique
    speaker list.
    """
    speakers: list[str] = []
    seen_speakers: set[str] = set()
    out: list[str] = []

    speaker_header_re = re.compile(
        r"^([A-Z][A-Za-z' .-]{1,40})\s*\(\s*\d{1,2}:\d{2}(?::\d{2})?\s*\)\s*$"
    )

    pending_speaker: str | None = None
    for raw in content.splitlines():
        line = raw.rstrip()
        if not line.strip():
            if pending_speaker is None:
                # Preserve paragraph breaks in fully plain text.
                if out and out[-1] != "":
                    out.append("")
            continue
        match = speaker_header_re.match(line.strip())
        if match:
            pending_speaker = match.group(1).strip()
            if pending_speaker not in seen_speakers:
                seen_speakers.add(pending_speaker)
                speakers.append(pending_speaker)
            continue
        if pending_speaker:
            out.append(f"{pending_speaker}: {line.strip()}")
            pending_speaker = None
            continue
        out.append(line.strip())

    return _join_dialog(out), speakers


# ---------- Helpers ----------


def _join_dialog(lines: list[str]) -> str:
    """Collapse adjacent identical-speaker lines into a single utterance,
    keep paragraph spacing minimal.
    """
    cleaned: list[str] = []
    for line in lines:
        if line == "":
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        # Merge adjacent same-speaker lines (Speaker: foo / Speaker: bar -> Speaker: foo bar).
        if cleaned and ":" in line and ":" in cleaned[-1]:
            prev_speaker, _ = cleaned[-1].split(":", 1)
            cur_speaker, _ = line.split(":", 1)
            if prev_speaker.strip() == cur_speaker.strip() and prev_speaker.strip():
                cleaned[-1] = f"{cleaned[-1].rstrip()} {line.split(':', 1)[1].strip()}"
                continue
        cleaned.append(line)
    # Trim trailing blanks
    while cleaned and cleaned[-1] == "":
        cleaned.pop()
    return "\n".join(cleaned)
