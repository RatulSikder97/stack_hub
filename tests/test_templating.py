"""Jinja2 master prompt rendering."""

from __future__ import annotations

import pytest
from jinja2.exceptions import UndefinedError

from pipeline.models import PostRecord, PostStatus
from pipeline.templating import (
    render_master_prompt,
    render_rotation_context,
    render_string,
)


def test_render_master_prompt_substitutes_all_tokens(tmp_project) -> None:  # noqa: ANN001
    rendered = render_master_prompt(brand_name="Acme", rotation=())
    assert "{{" not in rendered
    assert "Acme" in rendered
    assert "Sample synthesis paragraph" in rendered  # from voice_map
    assert "Sample promise" in rendered  # from brand_promise
    assert "Kill pattern alpha" in rendered  # from kill_list


def test_render_master_prompt_empty_rotation_message(tmp_project) -> None:  # noqa: ANN001
    rendered = render_master_prompt(brand_name="Acme")
    assert "No published posts yet" in rendered


def test_render_master_prompt_with_rotation(tmp_project) -> None:  # noqa: ANN001
    rotation = (
        PostRecord(
            post_id="20260201-a",
            status=PostStatus.PUBLISHED,
            hook_pattern_used="Counterintuitive Open",
            structural_framework_used="The Reversal",
            published_at="2026-02-01T00:00:00+00:00",
        ),
    )
    rendered = render_master_prompt(brand_name="Acme", rotation=rotation)
    assert "Counterintuitive Open" in rendered
    assert "The Reversal" in rendered


def test_render_string_strict_undefined() -> None:
    with pytest.raises(UndefinedError):
        render_string("hello {{ name }}")


def test_render_rotation_context_empty() -> None:
    text = render_rotation_context([])
    assert "No published posts yet" in text
