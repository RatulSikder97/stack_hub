"""Regex-based detector for the 6 kill-list patterns.

Runs without any API key — the safety net when no LLM is available, and the
fast pre-filter even when one is. Mirrors `voice/ai_tells_killlist.md`.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from pipeline.detectors.base import DetectionResult, Detector, Flag

# Patterns per kill list.
# 1. "It's not just X, it's Y" structures
# 2. "In a world where..." openings
# 3. Em-dashes used as stylistic flourish
# 4. "Let's explore..." / "Let's dive into..."
# 5. Three-item lists where two would do (heuristic: "X, Y, and Z" prose triplets)
# 6. Closing with "The choice is yours" / agency-handoff endings


@dataclass(frozen=True)
class _PatternRule:
    name: str
    regex: re.Pattern[str]
    closing_only: bool = False


_RULES: tuple[_PatternRule, ...] = (
    _PatternRule(
        name="its_not_just_x_its_y",
        regex=re.compile(
            r"\b(?:it'?s|its)\s+not\s+just\s+[^.,;\n]{1,80}[,.]?\s+(?:it'?s|its)\b",
            re.IGNORECASE,
        ),
    ),
    _PatternRule(
        name="in_a_world_where",
        regex=re.compile(r"\bin\s+a\s+world\s+where\b", re.IGNORECASE),
    ),
    _PatternRule(
        name="em_dash_stylistic_flourish",
        # Em-dash with whitespace on both sides — used as a stylistic break.
        regex=re.compile(r"(?<=\S)\s+—\s+(?=\S)|(?<=\S)—(?=\S)"),
    ),
    _PatternRule(
        name="lets_explore_or_dive_into",
        regex=re.compile(
            r"\blet'?s\s+(?:explore|dive\s+into|unpack|break\s+down|take\s+a\s+look)\b",
            re.IGNORECASE,
        ),
    ),
    _PatternRule(
        name="agency_handoff_close",
        regex=re.compile(
            r"\b(?:the\s+choice\s+is\s+yours|"
            r"it'?s\s+up\s+to\s+you|"
            r"you\s+decide|"
            r"the\s+rest\s+is\s+up\s+to\s+you)\b",
            re.IGNORECASE,
        ),
        closing_only=True,
    ),
)

# Triplet heuristic kept separate because it requires its own scan logic.
_TRIPLET_RE = re.compile(
    r"\b([A-Za-z][\w'-]+)\s*,\s+([A-Za-z][\w'-]+)\s*,\s+(?:and|or)\s+([A-Za-z][\w'-]+)\b"
)


class LocalKillListDetector(Detector):
    """Pure-Python detector covering all six kill-list patterns."""

    def detect(self, draft_text: str) -> DetectionResult:
        flags = list(self._scan(draft_text))
        return DetectionResult(flags=flags, passed=not flags)

    def _scan(self, draft_text: str) -> Iterator[Flag]:
        lines = draft_text.splitlines()
        last_meaningful = self._last_meaningful_line(lines)
        for index, line in enumerate(lines, start=1):
            yield from self._scan_line(
                line=line,
                index=index,
                in_close_window=index >= last_meaningful - 2,
            )
        yield from self._scan_triplets(draft_text, lines)

    @staticmethod
    def _last_meaningful_line(lines: list[str]) -> int:
        for idx in range(len(lines), 0, -1):
            if lines[idx - 1].strip() and not lines[idx - 1].lstrip().startswith("<!--"):
                return idx
        return len(lines)

    def _scan_line(
        self, *, line: str, index: int, in_close_window: bool
    ) -> Iterator[Flag]:
        for rule in _RULES:
            if rule.closing_only and not in_close_window:
                continue
            match = rule.regex.search(line)
            if match:
                yield Flag(
                    pattern=rule.name,
                    snippet=line.strip()[:240],
                    line_approx=index,
                )

    def _scan_triplets(self, draft_text: str, lines: list[str]) -> Iterator[Flag]:
        seen: set[str] = set()
        for match in _TRIPLET_RE.finditer(draft_text):
            triplet = match.group(0)
            if triplet.lower() in seen:
                continue
            seen.add(triplet.lower())
            line_idx = self._line_of_offset(draft_text, lines, match.start())
            yield Flag(
                pattern="three_item_list_where_two_would_do",
                snippet=triplet,
                line_approx=line_idx,
            )

    @staticmethod
    def _line_of_offset(text: str, lines: list[str], offset: int) -> int:
        running = 0
        for index, line in enumerate(lines, start=1):
            running += len(line) + 1  # +1 for the newline removed by splitlines
            if offset < running:
                return index
        return len(lines)
