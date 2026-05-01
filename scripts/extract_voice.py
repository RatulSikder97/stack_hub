#!/usr/bin/env python3
"""Regenerate voice/voice_map.md from the current corpus.

Uses the configured LLM provider when a key is available; otherwise produces
a deterministic local baseline so the file always reflects the actual corpus.
Run this whenever you swap or add to the corpus.
"""

from __future__ import annotations

import argparse
import sys

from pipeline import paths as _paths
from pipeline.config import get_settings
from pipeline.llm import MissingAPIKeyError, build_provider
from pipeline.logging_config import get_logger
from pipeline.paths import ensure_dirs
from pipeline.voice import VoiceExtractor

LOG = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate voice/voice_map.md from corpus")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Force local heuristic (skip provider call)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_dirs()
    settings = get_settings()

    provider = None
    if not args.local and settings.has_active_provider_key():
        try:
            provider = build_provider(settings)
            LOG.info("Extracting voice via %s", settings.llm_provider)
        except MissingAPIKeyError:
            LOG.warning("Provider key missing — local fallback")

    if provider is None:
        LOG.info("Extracting voice locally (no provider call)")

    extractor = VoiceExtractor(
        provider=provider,
        max_tokens=settings.llm_max_tokens_voice,
    )
    target = extractor.write_voice_map(_paths.VOICE_MAP_PATH)
    print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
