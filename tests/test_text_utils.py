"""LLM text utilities."""

from __future__ import annotations

from pipeline.llm.text_utils import strip_code_fences


def test_strip_plain_text() -> None:
    assert strip_code_fences("hello") == "hello"


def test_strip_with_language_tag() -> None:
    text = "```json\n{\"a\": 1}\n```"
    assert strip_code_fences(text) == '{"a": 1}'


def test_strip_without_language_tag() -> None:
    text = "```\n[1,2,3]\n```"
    assert strip_code_fences(text) == "[1,2,3]"


def test_strip_strips_whitespace() -> None:
    assert strip_code_fences("\n\n  hello  \n") == "hello"
