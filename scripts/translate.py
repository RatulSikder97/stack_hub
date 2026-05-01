#!/usr/bin/env python3
"""Standalone translation CLI.

Examples:
    python scripts/translate.py --text "ডিফল্ট সিদ্ধান্ত" --to en
    cat raw_idea.txt | python scripts/translate.py --to en
"""

from __future__ import annotations

import argparse
import sys

from pipeline.config import get_settings
from pipeline.llm import MissingAPIKeyError, build_provider
from pipeline.logging_config import get_logger
from pipeline.translation import Translator

LOG = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate text via configured LLM provider")
    parser.add_argument("--text", help="Text to translate. If omitted, reads stdin.")
    parser.add_argument("--to", default="en", help="Target language (ISO 639-1, default: en)")
    parser.add_argument(
        "--provenance",
        action="store_true",
        help="Print full provenance block (original + translated + detected source)",
    )
    return parser.parse_args(argv)


def _read_input(text_arg: str | None) -> str:
    if text_arg:
        return text_arg
    if sys.stdin.isatty():
        sys.stderr.write("Reading from stdin (Ctrl-D to end):\n")
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    text = _read_input(args.text)
    if not text.strip():
        LOG.error("No input text provided.")
        return 2

    settings = get_settings()
    if not settings.has_active_provider_key():
        LOG.error(
            "No API key for provider=%s. Set the corresponding key in .env.",
            settings.llm_provider,
        )
        return 2

    try:
        provider = build_provider(settings)
    except MissingAPIKeyError as exc:
        LOG.error("%s", exc)
        return 2

    result = Translator(provider, max_tokens=settings.llm_max_tokens_voice).translate(
        text, target_language=args.to
    )
    if args.provenance:
        print(result.render_provenance())
    else:
        print(result.translated_text)
    LOG.info(
        "Translated from %s to %s (needed_translation=%s)",
        result.source_language,
        result.target_language,
        result.needed_translation,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
