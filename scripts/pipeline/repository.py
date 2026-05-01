"""Persistence layer for `PostRecord`.

A thin repository over `data/posts.json` so callers depend on this interface
rather than the JSON file format directly. Atomic writes via temp-file rename
prevent half-written files if a process is killed mid-write.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path

from pipeline.models import PostRecord, PostStatus


class PostNotFoundError(KeyError):
    """Raised when a post_id does not exist in the repository."""


class PostRepository:
    """CRUD facade over a JSON-backed list of `PostRecord`."""

    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            from pipeline.paths import POSTS_PATH

            path = POSTS_PATH
        self._path: Path = path

    @property
    def path(self) -> Path:
        return self._path

    # --- Read ---------------------------------------------------------------

    def list(self) -> list[PostRecord]:
        if not self._path.exists():
            return []
        raw = json.loads(self._path.read_text(encoding="utf-8") or "[]")
        return [PostRecord.model_validate(item) for item in raw]

    def get(self, post_id: str) -> PostRecord:
        for post in self.list():
            if post.post_id == post_id:
                return post
        raise PostNotFoundError(post_id)

    def exists(self, post_id: str) -> bool:
        return any(p.post_id == post_id for p in self.list())

    def published(self) -> list[PostRecord]:
        return [p for p in self.list() if p.status == PostStatus.PUBLISHED]

    def recent_published(self, n: int = 3) -> list[PostRecord]:
        published = [p for p in self.published() if p.published_at]
        published.sort(key=lambda p: p.published_at or "", reverse=True)
        return published[:n]

    # --- Write --------------------------------------------------------------

    def save_all(self, posts: Iterable[PostRecord]) -> None:
        payload = [p.model_dump(mode="json") for p in posts]
        self._atomic_write(json.dumps(payload, indent=2) + "\n")

    def append(self, post: PostRecord) -> None:
        posts = self.list()
        if any(existing.post_id == post.post_id for existing in posts):
            raise ValueError(f"Duplicate post_id: {post.post_id}")
        posts.append(post)
        self.save_all(posts)

    def update(self, post_id: str, **fields: object) -> PostRecord:
        posts = self.list()
        for index, existing in enumerate(posts):
            if existing.post_id == post_id:
                updated = existing.model_copy(update=fields)
                posts[index] = updated
                self.save_all(posts)
                return updated
        raise PostNotFoundError(post_id)

    def replace(self, post: PostRecord) -> None:
        posts = self.list()
        for index, existing in enumerate(posts):
            if existing.post_id == post.post_id:
                posts[index] = post
                self.save_all(posts)
                return
        raise PostNotFoundError(post.post_id)

    # --- Internal -----------------------------------------------------------

    def _atomic_write(self, content: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, self._path)
