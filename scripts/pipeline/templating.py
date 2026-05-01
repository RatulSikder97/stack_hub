"""Jinja2-based prompt assembly.

The master system prompt lives in `prompts/master_system_prompt.md` with
`{{ token }}` placeholders. This module renders it by reading voice files,
brand promise, kill list, and rotation context, then substituting into the
template. Strict undefined → an unresolved token raises rather than silently
inserting an empty string into a draft request.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from jinja2 import Environment, StrictUndefined

from pipeline import paths as _paths
from pipeline.models import PostRecord


def _read_text(path: object) -> str:
    """Read file and strip trailing whitespace. Empty if missing."""
    from pathlib import Path

    p = Path(str(path))
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


def _section(text: str, header: str) -> str:
    """Extract markdown section starting at `## {header}` until next `## `."""
    lines = text.splitlines()
    out: list[str] = []
    capturing = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if capturing:
                break
            capturing = stripped[3:].strip().lower() == header.lower()
            continue
        if capturing:
            out.append(line)
    return "\n".join(out).strip()


def _build_env() -> Environment:
    return Environment(
        autoescape=False,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )


def render_master_prompt(
    *,
    brand_name: str,
    rotation: Sequence[PostRecord] = (),
    template_text: str | None = None,
) -> str:
    """Render the master system prompt with all 6 dynamic tokens populated.

    Tokens: brand_name, brand_promise, voice_synthesis, anti_voice, kill_list,
    rotation_context.
    """
    template_text = (
        template_text
        if template_text is not None
        else _paths.MASTER_PROMPT_PATH.read_text(encoding="utf-8")
    )

    voice_md = _read_text(_paths.VOICE_MAP_PATH)
    voice_synthesis = _section(voice_md, "Brand Voice Synthesis") or voice_md
    anti_voice = _section(voice_md, "Anti-Voice")

    context: dict[str, Any] = {
        "brand_name": brand_name,
        "brand_promise": _read_text(_paths.BRAND_PROMISE_PATH),
        "voice_synthesis": voice_synthesis,
        "anti_voice": anti_voice,
        "kill_list": _read_text(_paths.KILL_LIST_PATH),
        "rotation_context": render_rotation_context(rotation),
    }

    template = _build_env().from_string(template_text)
    return template.render(**context).strip() + "\n"


def render_rotation_context(rotation: Sequence[PostRecord]) -> str:
    """Format the last N published posts into a rotation snapshot."""
    if not rotation:
        return "No published posts yet — rotation constraints do not apply."
    lines = ["Last published posts (avoid repeating these patterns):"]
    for post in rotation:
        hook = post.hook_pattern_used or "(unspecified)"
        framework = post.structural_framework_used or "(unspecified)"
        lines.append(f"- {post.post_id}: hook={hook}, framework={framework}")
    return "\n".join(lines)


def render_string(template_text: str, **context: Any) -> str:
    """Render an arbitrary Jinja2 string with strict undefined handling."""
    return _build_env().from_string(template_text).render(**context)
