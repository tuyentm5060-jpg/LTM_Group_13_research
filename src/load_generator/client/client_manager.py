"""Coordinate concurrent TCP clients, aggregate latency/throughput metrics, and export CSV."""

from __future__ import annotations

import asyncio
from pathlib import Path
import time
from typing import Any, Callable

from ..metrics import BenchmarkSummary, RequestMetric, export_metrics_csv, summarize_metrics
from .tcp_client import DEFAULT_PAYLOAD_SIZE, ClientResult, run_client


async def run_many_clients(
    host: str,
    port: int,
    client_count: int,
    stop_event: Any = None,
    log_callback: Callable[[str], None] | None = None,
    *,
    requests_per_client: int = 100,
    payload_size: int = DEFAULT_PAYLOAD_SIZE,
    connect_timeout: float = 5.0,
    response_timeout: float = 5.0,
    think_time: float = 0.0,
    warmup_seconds: float = 0.0,
    measurement_seconds: float = 0.0,
    output_csv: str | Path | None = None,
    return_summary: bool = False,
) -> list[ClientResult] | tuple[list[ClientResult], BenchmarkSummary]:
    """
    Launch `client_count` concurrent asyncio TCP clients against `host:port`.

    - Supports optional warm-up phase (`warmup_seconds > 0`).
    - Supports either fixed request count per client (`requests_per_client`) or
      time-boxed measurement (`measurement_seconds > 0`).
    - Computes RTT (avg, min, max, p50, p95, p99), throughput (req/s), and error rate.
    - Exports per-request raw metrics to `output_csv` when provided.
    """
    def _log(msg: str) -> None:
        if log_callback is not None:
            log_callback(msg)

    # Optional warm-up phase (not recorded into final metrics)
    if warmup_seconds > 0 and not (stop_event is not None and stop_event.is_set()):
        _log(f"Warm-up phase: {warmup_seconds:.1f}s with {client_count} clients...")
        warmup_barrier = asyncio.Event()
        warmup_deadline = time.perf_counter() + warmup_seconds
        warmup_tasks = [
            asyncio.create_task(
                run_client(
                    client_id=i + 1,
                    host=host,
                    port=port,
                    stop_event=stop_event,
                    connect_timeout=connect_timeout,
                    response_timeout=response_timeout,
                    num_requests=10**9,
                    payload_size=payload_size,
                    think_time=think_time,
                    start_barrier=warmup_barrier,
                    deadline=warmup_deadline,
                    record_metrics=False,
                )
            )
            for i in range(client_count)
        ]
        await asyncio.sleep(min(0.1, 0.01 * client_count))
        warmup_barrier.set()
        await asyncio.gather(*warmup_tasks, return_exceptions=True)

    start_barrier = asyncio.Event()
    deadline = (time.perf_counter() + measurement_seconds) if measurement_seconds > 0 else None

    tasks = [
        asyncio.create_task(
            run_client(
                client_id=i + 1,
                host=host,
                port=port,
                stop_event=stop_event,
                connect_timeout=connect_timeout,
                response_timeout=response_timeout,
                num_requests=requests_per_client,
                payload_size=payload_size,
                think_time=think_time,
                start_barrier=start_barrier,
                deadline=deadline,
                record_metrics=True,
            )
        )
        for i in range(client_count)
    ]

    # Brief yield so sockets initiate TCP handshake before releasing the barrier
    await asyncio.sleep(min(0.15, 0.005 * client_count + 0.02))
    bench_start = time.perf_counter()
    start_barrier.set()

    results: list[ClientResult] = []
    for task in asyncio.as_completed(tasks):
        result = await task
        results.append(result)
        ok_reqs = sum(1 for m in result.metrics if m.status == "OK")
        avg_client_rtt = (
            sum(m.rtt_ms for m in result.metrics if m.status == "OK") / ok_reqs
            if ok_reqs > 0 else 0.0
        )
        _log(
            f"Client {result.client_id:03d} | {result.status} | "
            f"ok={ok_reqs} | avg_rtt={avg_client_rtt:.3f}ms | {result.detail}"
        )

    bench_duration = time.perf_counter() - bench_start
    results.sort(key=lambda r: r.client_id)

    all_metrics: list[RequestMetric] = [
        m for res in results for m in res.metrics
    ]
    all_metrics.sort(key=lambda m: (m.timestamp, m.client_id, m.seq))

    summary = summarize_metrics(
        metrics=all_metrics,
        clients=client_count,
        requests_per_client=requests_per_client,
        duration_seconds=bench_duration,
    )

    if output_csv:
        saved_path = export_metrics_csv(all_metrics, output_csv)
        _log(f"Exported {len(all_metrics)} raw metric rows -> {saved_path}")

    _log(
        f"SUMMARY | clients={summary.clients} | total={summary.total_requests} | "
        f"ok={summary.success_count} | err={summary.error_count} ({summary.error_rate_pct:.2f}%) | "
        f"throughput={summary.throughput_rps:.2f} req/s | "
        f"avg_rtt={summary.avg_rtt_ms:.3f}ms | p95={summary.p95_rtt_ms:.3f}ms | p99={summary.p99_rtt_ms:.3f}ms"
    )

    if return_summary:
        return results, summary
    return results
