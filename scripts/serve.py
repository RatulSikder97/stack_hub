#!/usr/bin/env python3
"""Launch the local web panel.

Defaults to port 8765 (8000 is too commonly taken by Docker / dev tools).
If the chosen port is already in use, automatically searches the next 20
ports for a free one before giving up.

Usage:
    python scripts/serve.py             # http://localhost:8765 (or next free)
    python scripts/serve.py --port 9000 # explicit port
    python scripts/serve.py --host 0.0.0.0 --port 8765   # LAN access
    python scripts/serve.py --strict-port               # fail if port busy
"""

from __future__ import annotations

import argparse
import socket
import sys

from pipeline.logging_config import get_logger

LOG = get_logger(__name__)

DEFAULT_PORT = 8765
PORT_SEARCH_RANGE = 20


def is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def find_free_port(host: str, starting_port: int, *, span: int = PORT_SEARCH_RANGE) -> int:
    for offset in range(span):
        candidate = starting_port + offset
        if is_port_free(host, candidate):
            return candidate
    raise RuntimeError(
        f"No free port in {starting_port}-{starting_port + span - 1} on {host}"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Stack Hub web panel")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Preferred port (default: {DEFAULT_PORT}; auto-bumps if busy)",
    )
    parser.add_argument(
        "--strict-port",
        action="store_true",
        help="Refuse to auto-search for a free port; fail loudly if --port is busy",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Auto-reload on file changes (dev mode)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    port = args.port
    if not is_port_free(args.host, port):
        if args.strict_port:
            LOG.error(
                "Port %d on %s is busy. Pick another with --port, "
                "or drop --strict-port to auto-search.",
                port, args.host,
            )
            return 1
        try:
            port = find_free_port(args.host, args.port)
        except RuntimeError as exc:
            LOG.error("%s", exc)
            return 1
        LOG.warning("Port %d busy — using %d instead.", args.port, port)

    import uvicorn

    LOG.info("Web panel: http://%s:%d", args.host, port)
    LOG.info("Press Ctrl-C to stop.")
    uvicorn.run(
        "pipeline.web.api:create_app",
        host=args.host,
        port=port,
        factory=True,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
