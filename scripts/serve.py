#!/usr/bin/env python3
"""Launch the local web panel.

Usage:
    python scripts/serve.py             # http://localhost:8000
    python scripts/serve.py --port 8080
    python scripts/serve.py --host 0.0.0.0 --port 8000   # LAN access
"""

from __future__ import annotations

import argparse
import sys

from pipeline.logging_config import get_logger

LOG = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Stack Hub web panel")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Auto-reload on file changes (dev mode)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    import uvicorn

    LOG.info("Web panel: http://%s:%d", args.host, args.port)
    uvicorn.run(
        "pipeline.web.api:create_app",
        host=args.host,
        port=args.port,
        factory=True,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
