"""Transcript parser — VTT, SRT, plain text, Google Meet copy/paste."""

from __future__ import annotations

from pipeline.transcript import detect_format, parse


def test_detect_format_vtt() -> None:
    assert detect_format("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nhi\n") == "vtt"


def test_detect_format_srt() -> None:
    sample = "1\n00:00:01,000 --> 00:00:02,000\nhi\n"
    assert detect_format(sample) == "srt"


def test_detect_format_plain() -> None:
    assert detect_format("Hello world") == "text"


def test_vtt_strips_timestamps_and_keeps_speakers() -> None:
    sample = (
        "WEBVTT\n\n"
        "1\n"
        "00:00:00.000 --> 00:00:05.000\n"
        "<v Alice>Welcome to the meeting.\n\n"
        "2\n"
        "00:00:05.000 --> 00:00:08.000\n"
        "<v Bob>Thanks for having me.\n"
    )
    result = parse(sample)
    assert result.detected_format == "vtt"
    assert "Welcome to the meeting." in result.text
    assert "Thanks for having me." in result.text
    assert "00:00:00" not in result.text
    assert result.speakers == ["Alice", "Bob"]


def test_srt_strips_cue_numbers_and_timestamps() -> None:
    sample = (
        "1\n"
        "00:00:00,000 --> 00:00:05,000\n"
        "Welcome to the meeting.\n\n"
        "2\n"
        "00:00:05,000 --> 00:00:08,000\n"
        "Thanks for having me.\n"
    )
    result = parse(sample)
    assert result.detected_format == "srt"
    assert "Welcome to the meeting." in result.text
    assert "00:00:00" not in result.text


def test_google_meet_copy_paste_format() -> None:
    sample = (
        "Alice (00:00)\n"
        "Welcome to the meeting.\n\n"
        "Bob (00:05)\n"
        "Thanks for having me.\n"
    )
    result = parse(sample)
    assert result.detected_format == "text"
    assert "Alice: Welcome to the meeting." in result.text
    assert "Bob: Thanks for having me." in result.text
    assert result.speakers == ["Alice", "Bob"]


def test_merges_consecutive_lines_from_same_speaker() -> None:
    sample = (
        "WEBVTT\n\n"
        "1\n00:00:00.000 --> 00:00:03.000\n<v Alice>Sentence one.\n\n"
        "2\n00:00:03.000 --> 00:00:06.000\n<v Alice>Sentence two.\n\n"
        "3\n00:00:06.000 --> 00:00:09.000\n<v Bob>Different speaker.\n"
    )
    result = parse(sample)
    # Adjacent Alice lines should fold into one utterance.
    alice_count = result.text.count("Alice:")
    assert alice_count == 1
    assert "Sentence one. Sentence two." in result.text
    assert "Bob: Different speaker." in result.text


def test_plain_text_passes_through() -> None:
    sample = "Some idea I want to think about. This is the second sentence."
    result = parse(sample)
    assert result.detected_format == "text"
    assert result.text == sample
    assert result.speakers == []


def test_empty_input_returns_empty() -> None:
    result = parse("")
    assert result.text == ""
    assert result.line_count == 0
    assert result.word_count == 0


def test_word_and_line_counts() -> None:
    # Speaker label is preserved in text, so it counts as a token.
    sample = "WEBVTT\n\n1\n00:00:00.000 --> 00:00:02.000\n<v A>One two three.\n"
    result = parse(sample)
    assert result.text == "A: One two three."
    assert result.word_count == 4  # "A:", "One", "two", "three."
    assert result.line_count == 1


def test_strips_html_in_vtt() -> None:
    sample = (
        "WEBVTT\n\n"
        "1\n00:00:00.000 --> 00:00:02.000\n"
        "<v Alice><b>Hello</b> <i>there</i>.\n"
    )
    result = parse(sample)
    assert "<b>" not in result.text
    assert "Hello there." in result.text
