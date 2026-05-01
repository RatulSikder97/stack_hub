"""Single source of truth for filesystem paths.

Resolved once at import time so the rest of the codebase never recomputes them.
The project root is two levels up from this file (`scripts/pipeline/paths.py`).
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT: Path = Path(
    os.environ.get("STACK_HUB_ROOT", "")
).resolve() if os.environ.get("STACK_HUB_ROOT") else Path(__file__).resolve().parents[2]

# Top-level dirs.
CORPUS_DIR: Path = PROJECT_ROOT / "corpus"
VOICE_DIR: Path = PROJECT_ROOT / "voice"
PROMPTS_DIR: Path = PROJECT_ROOT / "prompts"
LIBRARIES_DIR: Path = PROJECT_ROOT / "libraries"
BRIEFS_DIR: Path = PROJECT_ROOT / "briefs"
DRAFTS_DIR: Path = PROJECT_ROOT / "drafts"
PUBLISHED_DIR: Path = PROJECT_ROOT / "published"
DATA_DIR: Path = PROJECT_ROOT / "data"
RITUALS_DIR: Path = PROJECT_ROOT / "rituals"
AUDITS_DIR: Path = RITUALS_DIR / "audits"
GROWTH_DIR: Path = PROJECT_ROOT / "growth"

# Specific files.
POSTS_PATH: Path = DATA_DIR / "posts.json"
CONFIG_PATH: Path = DATA_DIR / "config.json"
ENV_PATH: Path = PROJECT_ROOT / ".env"

# Prompt + voice files.
MASTER_PROMPT_PATH: Path = PROMPTS_DIR / "master_system_prompt.md"
DETECTOR_PROMPT_PATH: Path = PROMPTS_DIR / "ai_tells_detector_prompt.md"
VOICE_MAP_PATH: Path = VOICE_DIR / "voice_map.md"
BRAND_PROMISE_PATH: Path = VOICE_DIR / "brand_promise.md"
KILL_LIST_PATH: Path = VOICE_DIR / "ai_tells_killlist.md"

# Library files.
HOOK_LIBRARY_PATH: Path = LIBRARIES_DIR / "hook_library.md"
STRUCTURE_LIBRARY_PATH: Path = LIBRARIES_DIR / "structure_library.md"

# Brief template.
BRIEF_TEMPLATE_PATH: Path = BRIEFS_DIR / "_TEMPLATE.md"


def ensure_dirs() -> None:
    """Create all expected directories if missing. Idempotent."""
    for path in (
        CORPUS_DIR,
        VOICE_DIR,
        PROMPTS_DIR,
        LIBRARIES_DIR,
        BRIEFS_DIR,
        DRAFTS_DIR,
        PUBLISHED_DIR,
        DATA_DIR,
        RITUALS_DIR,
        AUDITS_DIR,
        GROWTH_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
