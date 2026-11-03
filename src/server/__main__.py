"""Run python -m server with src on PYTHONPATH."""

import argparse
import asyncio
import logging

from .app import ServerConfig, serve


def main():
    parser = argparse.ArgumentParser(description="TCP echo research server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--max-payload-bytes", type=int, default=65536)
    args = parser.parse_args()
    try:
        config = ServerConfig(args.host, args.port, args.timeout, args.max_payload_bytes)
    except ValueError as exc:
        parser.error(str(exc))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(serve(config))
    except KeyboardInterrupt:
        logging.info("Server stopped")
    except OSError as exc:
        parser.exit(1, f"Cannot start server: {exc}\n")


if __name__ == "__main__":
    main()
