"""Asyncio TCP client supporting multi-request closed-loop load and RTT measurement."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import time
from typing import Any
import uuid

from common.protocol import ProtocolError, encode_message, read_message
from ..metrics import RequestMetric

DEFAULT_PAYLOAD_SIZE = 1024


@dataclass
class ClientResult:
    client_id: int
    request_id: str
    status: str
    detail: str
    metrics: list[RequestMetric] = field(default_factory=list)


def build_request(payload_size: int = DEFAULT_PAYLOAD_SIZE, request_id: str | None = None) -> dict[str, str]:
    """Create a unique requestId and a UTF-8 payload of exact byte length."""
    if payload_size < 0:
        raise ValueError("payload_size must be non-negative")
    payload = "A" * payload_size
    req_id = request_id or str(uuid.uuid4())
    return {"requestId": req_id, "payload": payload}


def _is_stopped(stop_event: Any) -> bool:
    return bool(stop_event is not None and stop_event.is_set())


async def run_client(
    client_id: int,
    host: str,
    port: int,
    stop_event: Any = None,
    connect_timeout: float = 5.0,
    response_timeout: float = 5.0,
    num_requests: int = 1,
    payload_size: int = DEFAULT_PAYLOAD_SIZE,
    think_time: float = 0.0,
    start_barrier: asyncio.Event | None = None,
    deadline: float | None = None,
    record_metrics: bool = True,
) -> ClientResult:
    """
    Open a single TCP connection and send requests in closed-loop (or with think_time),
    measuring per-request RTT in milliseconds.

    If `deadline` (monotonic timestamp from `time.perf_counter()`) is provided,
    requests continue until `time.perf_counter() >= deadline` or `stop_event` is set.
    Otherwise, sends `num_requests` sequential requests.
    """
    metrics: list[RequestMetric] = []
    writer: asyncio.StreamWriter | None = None
    last_request_id = ""
    payload_str = "A" * payload_size

    if _is_stopped(stop_event):
        return ClientResult(client_id, "", "STOPPED", "Stopped before connect", metrics)

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=connect_timeout
        )
    except asyncio.TimeoutError:
        if record_metrics:
            metrics.append(
                RequestMetric(client_id, "", 0, time.time(), -1.0, payload_size, "CONN_ERROR", "Connection timeout")
            )
        return ClientResult(client_id, "", "FAILED", "Connection timeout", metrics)
    except OSError as exc:
        if record_metrics:
            metrics.append(
                RequestMetric(client_id, "", 0, time.time(), -1.0, payload_size, "CONN_ERROR", str(exc))
            )
        return ClientResult(client_id, "", "FAILED", f"Connection error: {exc}", metrics)
    except Exception as exc:
        if record_metrics:
            metrics.append(
                RequestMetric(client_id, "", 0, time.time(), -1.0, payload_size, "ERROR", str(exc))
            )
        return ClientResult(client_id, "", "FAILED", f"Unexpected connect error: {exc}", metrics)

    try:
        if start_barrier is not None:
            await start_barrier.wait()

        seq = 0
        while True:
            if _is_stopped(stop_event):
                if not metrics:
                    return ClientResult(client_id, last_request_id, "STOPPED", "Stopped before send", metrics)
                break

            if deadline is not None:
                if time.perf_counter() >= deadline:
                    break
            else:
                if seq >= num_requests:
                    break

            seq += 1
            request_id = f"c{client_id}-r{seq}-{uuid.uuid4().hex[:8]}"
            last_request_id = request_id
            request = {"requestId": request_id, "payload": payload_str}
            frame = encode_message(request)

            send_wall_ts = time.time()
            t0 = time.perf_counter()

            try:
                writer.write(frame)
                await asyncio.wait_for(writer.drain(), timeout=response_timeout)
                response = await asyncio.wait_for(
                    read_message(reader, max(payload_size, 65536)), timeout=response_timeout
                )
                t1 = time.perf_counter()
                rtt_ms = (t1 - t0) * 1000.0

                if response["requestId"] != request_id:
                    if record_metrics:
                        metrics.append(
                            RequestMetric(
                                client_id, request_id, seq, send_wall_ts, round(rtt_ms, 4),
                                payload_size, "MISMATCH", "Response requestId mismatch"
                            )
                        )
                    return ClientResult(
                        client_id, request_id, "FAILED",
                        "Response requestId does not match", metrics
                    )

                if response["payload"] != payload_str:
                    if record_metrics:
                        metrics.append(
                            RequestMetric(
                                client_id, request_id, seq, send_wall_ts, round(rtt_ms, 4),
                                payload_size, "MISMATCH", "Response payload mismatch"
                            )
                        )
                    return ClientResult(
                        client_id, request_id, "FAILED",
                        "Response payload does not match", metrics
                    )

                if record_metrics:
                    metrics.append(
                        RequestMetric(
                            client_id, request_id, seq, send_wall_ts, round(rtt_ms, 4),
                            payload_size, "OK", ""
                        )
                    )

            except (asyncio.TimeoutError, TimeoutError):
                if record_metrics:
                    metrics.append(
                        RequestMetric(
                            client_id, request_id, seq, send_wall_ts, -1.0,
                            payload_size, "TIMEOUT", "Response timeout"
                        )
                    )
                return ClientResult(
                    client_id, request_id, "FAILED",
                    "Timeout sending request or waiting for complete response", metrics
                )
            except asyncio.IncompleteReadError:
                if record_metrics:
                    metrics.append(
                        RequestMetric(
                            client_id, request_id, seq, send_wall_ts, -1.0,
                            payload_size, "INCOMPLETE_READ", "Server closed connection early"
                        )
                    )
                return ClientResult(
                    client_id, request_id, "FAILED",
                    "Server closed connection before a complete response was received", metrics
                )
            except ProtocolError as exc:
                if record_metrics:
                    metrics.append(
                        RequestMetric(
                            client_id, request_id, seq, send_wall_ts, -1.0,
                            payload_size, "PROTOCOL_ERROR", str(exc)
                        )
                    )
                return ClientResult(
                    client_id, request_id, "FAILED", f"Invalid response: {exc}", metrics
                )
            except OSError as exc:
                if record_metrics:
                    metrics.append(
                        RequestMetric(
                            client_id, request_id, seq, send_wall_ts, -1.0,
                            payload_size, "CONN_ERROR", str(exc)
                        )
                    )
                return ClientResult(
                    client_id, request_id, "FAILED", f"Connection error: {exc}", metrics
                )
            except Exception as exc:
                if record_metrics:
                    metrics.append(
                        RequestMetric(
                            client_id, request_id, seq, send_wall_ts, -1.0,
                            payload_size, "ERROR", str(exc)
                        )
                    )
                return ClientResult(
                    client_id, request_id, "FAILED", f"Unexpected error: {exc}", metrics
                )

            if think_time > 0:
                if deadline is not None and (time.perf_counter() + think_time) >= deadline:
                    break
                await asyncio.sleep(think_time)

        ok_count = sum(1 for m in metrics if m.status == "OK")
        if _is_stopped(stop_event) and ok_count < num_requests and deadline is None:
            return ClientResult(
                client_id, last_request_id, "STOPPED",
                f"Stopped after {ok_count}/{num_requests} requests", metrics
            )
        return ClientResult(
            client_id, last_request_id, "SUCCESS",
            f"Completed {ok_count} requests", metrics
        )
    finally:
        if writer is not None:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=response_timeout)
            except Exception:
                pass
