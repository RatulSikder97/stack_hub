from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
POSTS_PATH = DATA_DIR / "posts.json"
CONFIG_PATH = DATA_DIR / "config.json"


class PostRecord(BaseModel):
    post_id: str
    working_title: str = ""
    niche: str = ""
    hook_pattern_used: str = ""
    structural_framework_used: str = ""
    status: str = "idea"
    publish_date: str | None = None
    open_loop_resolved: bool = False
    ai_tells_check_passed: bool = False
    human_edit_completed: bool = False
    share_count: int = 0
    open_rate: float = 0.0
    substack_url: str = ""
    created_at: str = Field(default_factory=lambda: now_iso())
    published_at: str | None = None
    retention_check_answers: list[dict[str, Any]] = Field(default_factory=list)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_posts() -> list[PostRecord]:
    if not POSTS_PATH.exists():
        return []
    raw = json.loads(POSTS_PATH.read_text())
    return [PostRecord.model_validate(item) for item in raw]


def save_posts(posts: list[PostRecord]) -> None:
    POSTS_PATH.write_text(json.dumps([p.model_dump() for p in posts], indent=2) + "\n")


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"cadence_days": 7, "brand_name": "ASK_ME_UPDATE_ME"}
    return json.loads(CONFIG_PATH.read_text())


def get_post(posts: list[PostRecord], post_id: str) -> PostRecord:
    for post in posts:
        if post.post_id == post_id:
            return post
    raise ValueError(f"post_id not found: {post_id}")
