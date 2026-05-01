"""Small helpers for normalizing LLM text output."""

from __future__ import annotations


def strip_code_fences(text: str) -> str:
    """Remove leading/trailing triple-backtick code fences from a model response."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
