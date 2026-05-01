"""Centralized logger setup.

CLI scripts call `get_logger(__name__)` instead of using bare `print()` for
non-output messages. Stdout stays clean for piping. Stderr handles diagnostics.
"""

from __future__ import annotations

import logging
import os
import sys

_CONFIGURED = False
_DEFAULT_LEVEL = logging.INFO
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"


def _configure_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level_name = os.environ.get("STACK_HUB_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, _DEFAULT_LEVEL)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S%z"))
    root = logging.getLogger("pipeline")
    root.setLevel(level)
    root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a child logger of the pipeline root logger."""
    _configure_root()
    if not name.startswith("pipeline"):
        name = f"pipeline.{name}"
    return logging.getLogger(name)
