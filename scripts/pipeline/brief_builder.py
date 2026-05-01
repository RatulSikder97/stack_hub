"""Compose a populated brief from a raw idea in any language.

Pipeline:
1. Optionally translate the idea into English via `Translator`.
2. Ask the LLM, anchored on the brand voice + libraries, to generate
   strategic brief content (working title + 6 sections).
3. Return a `BriefDraft` the CLI can serialize to disk.

This module is what makes the "type in Bengali → fully populated brief"
loop possible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from pipeline import paths as _paths
from pipeline.llm.base import LLMProvider
from pipeline.llm.text_utils import strip_code_fences
from pipeline.translation import TranslationResult, Translator


class BriefBuildError(RuntimeError):
    """Raised when the LLM cannot produce a usable brief payload."""


@dataclass(frozen=True)
class BriefDraft:
    working_title: str
    one_big_idea: str
    why_now: str
    target_hook: str
    target_framework: str
    reader_transformation: str
    forbidden_moves: list[str]
    translation: TranslationResult | None

    def render(self) -> str:
        forbidden = "\n".join(f"- {move}" for move in self.forbidden_moves) or "- (none)"
        provenance = self.translation.render_provenance() if self.translation else ""
        provenance_block = (
            f"\n## Source Idea\n\n{provenance}\n" if provenance else ""
        )
        return (
            "# Brief\n\n"
            f"## Working Title\n{self.working_title}\n\n"
            f"## One Big Idea\n{self.one_big_idea}\n\n"
            f"## Why this why now\n{self.why_now}\n\n"
            f"## Target hook pattern\n{self.target_hook}\n\n"
            f"## Target structural framework\n{self.target_framework}\n\n"
            f"## Reader Transformation\n{self.reader_transformation}\n\n"
            f"## Forbidden Moves\n{forbidden}\n"
            f"{provenance_block}"
        )


_SYSTEM_PROMPT_TEMPLATE = (
    "You are an editorial strategist for the Substack brand below. From a "
    "raw idea (already translated to English), produce a strategic brief in "
    "JSON. Anchor working title and One Big Idea in the brand's voice. "
    "Pick exactly one hook pattern from the hook menu and exactly one "
    "framework from the structure menu, choosing whatever best fits the idea.\n\n"
    "Brand promise:\n{brand_promise}\n\n"
    "Voice synthesis:\n{voice_synthesis}\n\n"
    "Hook menu (pattern names only):\n{hook_names}\n\n"
    "Structure menu (framework names only):\n{framework_names}\n\n"
    'Return ONLY this JSON shape with no prose, no code fences:\n'
    '{{\n'
    '  "working_title": "<6-12 words>",\n'
    '  "one_big_idea": "<single sentence, no qualifiers>",\n'
    '  "why_now": "<2-3 sentences explaining timeliness>",\n'
    '  "target_hook": "<one of the hook menu names>",\n'
    '  "target_framework": "<one of the framework menu names>",\n'
    '  "reader_transformation": "<2-3 sentences on what the reader walks away with>",\n'
    '  "forbidden_moves": ["<short rule>", "<short rule>", "<short rule>"]\n'
    '}}'
)


_HOOK_NAMES = (
    "Counterintuitive Open",
    "Specific Image",
    "Number Anchor",
    "Confession",
    "Question Sharpened",
    "False Choice",
    "Quote Pivot",
    "Tiny Story",
    "Definition Reframe",
    "Historical Hook",
    "Conversation Snippet",
    "Promise + Setup",
)

_FRAMEWORK_NAMES = (
    "The Concept Lens",
    "The Three Examples",
    "The Reversal",
    "The Personal Investigation",
    "The Listicle Done Right",
    "The Letter",
)


class IdeaToBrief:
    """Compose a populated brief from a raw idea."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        translator: Translator | None = None,
        max_tokens: int = 4000,
    ) -> None:
        self._provider = provider
        self._translator = translator or Translator(provider, max_tokens=max_tokens)
        self._max_tokens = max_tokens

    def build(self, idea_text: str, *, target_language: str = "en") -> BriefDraft:
        if not idea_text or not idea_text.strip():
            raise ValueError("idea_text cannot be empty")

        translation = self._translator.translate(
            idea_text, target_language=target_language
        )
        english_idea = translation.translated_text

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            brand_promise=self._read(_paths.BRAND_PROMISE_PATH),
            voice_synthesis=self._extract_voice_synthesis(),
            hook_names="\n".join(f"- {h}" for h in _HOOK_NAMES),
            framework_names="\n".join(f"- {f}" for f in _FRAMEWORK_NAMES),
        )

        raw = self._provider.generate(
            system_prompt,
            f"Raw idea:\n{english_idea}",
            max_tokens=self._max_tokens,
            temperature=0.4,
        )
        cleaned = strip_code_fences(raw)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise BriefBuildError(
                f"Brief builder returned non-JSON:\n{raw[:400]}"
            ) from exc
        if not isinstance(payload, dict):
            raise BriefBuildError(f"Brief builder returned {type(payload).__name__}")

        return BriefDraft(
            working_title=str(payload.get("working_title", "")).strip(),
            one_big_idea=str(payload.get("one_big_idea", "")).strip(),
            why_now=str(payload.get("why_now", "")).strip(),
            target_hook=str(payload.get("target_hook", "")).strip(),
            target_framework=str(payload.get("target_framework", "")).strip(),
            reader_transformation=str(
                payload.get("reader_transformation", "")
            ).strip(),
            forbidden_moves=[
                str(item).strip()
                for item in payload.get("forbidden_moves", [])
                if str(item).strip()
            ],
            translation=translation,
        )

    @staticmethod
    def _read(path: object) -> str:
        from pathlib import Path

        p = Path(str(path))
        if not p.exists():
            return ""
        return p.read_text(encoding="utf-8").strip()

    def _extract_voice_synthesis(self) -> str:
        text = self._read(_paths.VOICE_MAP_PATH)
        if "## Brand Voice Synthesis" not in text:
            return text
        # Extract just the synthesis section to keep the prompt tight.
        section = text.split("## Brand Voice Synthesis", 1)[1]
        return section.split("##", 1)[0].strip()
