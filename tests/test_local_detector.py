"""LocalKillListDetector covers all six kill-list patterns."""

from __future__ import annotations

import pytest

from pipeline.detectors import LocalKillListDetector


@pytest.fixture
def detector() -> LocalKillListDetector:
    return LocalKillListDetector()


def test_clean_draft_passes(detector: LocalKillListDetector) -> None:
    text = (
        "A short paragraph that opens cleanly.\n\n"
        "Then a line with content but no banned phrases.\n\n"
        "Closing thought worth saving.\n"
    )
    result = detector.detect(text)
    assert result.passed
    assert result.flags == []


def test_in_a_world_where_caught(detector: LocalKillListDetector) -> None:
    result = detector.detect("In a world where attention is scarce, focus wins.\n")
    patterns = {f.pattern for f in result.flags}
    assert "in_a_world_where" in patterns
    assert not result.passed


def test_its_not_just_x_its_y_caught(detector: LocalKillListDetector) -> None:
    result = detector.detect("It's not just hard, it's nearly impossible.\n")
    patterns = {f.pattern for f in result.flags}
    assert "its_not_just_x_its_y" in patterns


def test_lets_explore_dive_into_caught(detector: LocalKillListDetector) -> None:
    result = detector.detect("Let's dive into the framework.\n")
    patterns = {f.pattern for f in result.flags}
    assert "lets_explore_or_dive_into" in patterns


def test_em_dash_stylistic_flourish_caught(detector: LocalKillListDetector) -> None:
    result = detector.detect("That moment — when nothing makes sense — passes.\n")
    patterns = {f.pattern for f in result.flags}
    assert "em_dash_stylistic_flourish" in patterns


def test_three_item_list_caught(detector: LocalKillListDetector) -> None:
    result = detector.detect("It is fast, cheap, and reliable.\n")
    patterns = {f.pattern for f in result.flags}
    assert "three_item_list_where_two_would_do" in patterns


def test_agency_handoff_only_at_close(detector: LocalKillListDetector) -> None:
    body_text = (
        "The choice is yours, the writer says, but the post continues.\n\n"
        "More argument follows here.\n\n"
        "And here.\n\n"
        "And a real ending sentence.\n"
    )
    result = detector.detect(body_text)
    patterns = {f.pattern for f in result.flags}
    # In body, not last 3 lines: should NOT trigger agency handoff.
    assert "agency_handoff_close" not in patterns


def test_agency_handoff_caught_in_close(detector: LocalKillListDetector) -> None:
    text = "Body line.\n\nAnother body line.\n\nThe choice is yours.\n"
    result = detector.detect(text)
    patterns = {f.pattern for f in result.flags}
    assert "agency_handoff_close" in patterns


def test_all_six_patterns_in_one_draft(detector: LocalKillListDetector) -> None:
    text = (
        "In a world where focus is rare, our protocol shines.\n\n"
        "It's not just hard, it's nearly impossible.\n\n"
        "Let's dive into the model — quickly, deeply, fully.\n\n"
        "You should know red, white, and blue.\n\n"
        "The choice is yours.\n"
    )
    result = detector.detect(text)
    patterns = {f.pattern for f in result.flags}
    expected = {
        "in_a_world_where",
        "its_not_just_x_its_y",
        "lets_explore_or_dive_into",
        "em_dash_stylistic_flourish",
        "three_item_list_where_two_would_do",
        "agency_handoff_close",
    }
    assert expected <= patterns
