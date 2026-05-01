"""Domain models for the content pipeline.

Pydantic v2 enforces schema on read AND write, so a missing or misnamed field
in `data/posts.json` fails loudly the next time something loads it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PostStatus(StrEnum):
    """Lifecycle states for a post."""

    IDEA = "idea"
    BRIEF = "brief"
    DRAFTING = "drafting"
    AI_TELLS_PASS = "ai_tells_pass"
    EDITING = "editing"
    RETENTION_CHECK = "retention_check"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"


def now_iso() -> str:
    """UTC ISO 8601 timestamp string."""
    return datetime.now(timezone.utc).isoformat()


class RetentionAnswer(BaseModel):
    """One answer in the human retention checklist."""

    model_config = ConfigDict(extra="forbid")

    question: str
    passed: bool


class PostRecord(BaseModel):
    """The 16-field post record stored in `data/posts.json`.

    Fields: post_id, working_title, niche, hook_pattern_used,
    structural_framework_used, status, publish_date, open_loop_resolved,
    ai_tells_check_passed, human_edit_completed, share_count, open_rate,
    substack_url, created_at, published_at, retention_check_answers.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    post_id: str
    working_title: str = ""
    niche: str = ""
    hook_pattern_used: str = ""
    structural_framework_used: str = ""
    status: PostStatus = PostStatus.IDEA
    publish_date: str | None = None
    open_loop_resolved: bool = False
    ai_tells_check_passed: bool = False
    human_edit_completed: bool = False
    share_count: int = Field(default=0, ge=0)
    open_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    substack_url: str = ""
    created_at: str = Field(default_factory=now_iso)
    published_at: str | None = None
    retention_check_answers: list[RetentionAnswer] = Field(default_factory=list)

    @field_validator("post_id")
    @classmethod
    def _post_id_nonempty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("post_id must not be empty")
        return value

    @field_validator("substack_url")
    @classmethod
    def _substack_url_format(cls, value: str) -> str:
        if value and not value.startswith(("http://", "https://")):
            raise ValueError("substack_url must start with http:// or https://")
        return value

    def with_status(self, status: PostStatus) -> Self:
        """Return a copy with status updated. Pydantic frozen-style helper."""
        return self.model_copy(update={"status": status})
