"""Bridge between GUI/CLI entrypoints and the asyncio load generator engine."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from .client.client_manager import run_many_clients
from .client.tcp_client import DEFAULT_PAYLOAD_SIZE


def run_generator(
    host: str,
    port: int,
    client_count: int,
    stop_event: Any = None,
    log_callback: Callable[[str], None] | None = None,
    *,
    requests_per_client: int = 100,
    payload_size: int = DEFAULT_PAYLOAD_SIZE,
    timeout: float = 5.0,
    think_time: float = 0.0,
    warmup_seconds: float = 0.0,
    measurement_seconds: float = 0.0,
    output_csv: str | Path | None = None,
    return_summary: bool = False,
):
    """Run the asyncio load generator event loop."""
    return asyncio.run(
        run_many_clients(
            host=host,
            port=port,
            client_count=client_count,
            stop_event=stop_event,
            log_callback=log_callback,
            requests_per_client=requests_per_client,
            payload_size=payload_size,
            connect_timeout=timeout,
            response_timeout=timeout,
            think_time=think_time,
            warmup_seconds=warmup_seconds,
            measurement_seconds=measurement_seconds,
            output_csv=output_csv,
            return_summary=return_summary,
        )
    )
