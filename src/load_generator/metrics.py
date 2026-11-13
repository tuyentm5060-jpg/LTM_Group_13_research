"""Latency, throughput, error rate calculations and raw CSV export."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
import statistics
from typing import Iterable, Sequence


@dataclass(frozen=True)
class RequestMetric:
    client_id: int
    request_id: str
    seq: int
    timestamp: float
    rtt_ms: float
    payload_bytes: int
    status: str  # OK | TIMEOUT | MISMATCH | INCOMPLETE_READ | PROTOCOL_ERROR | CONN_ERROR | STOPPED | ERROR
    error_detail: str = ""


@dataclass(frozen=True)
class BenchmarkSummary:
    clients: int
    requests_per_client: int
    total_requests: int
    success_count: int
    error_count: int
    duration_seconds: float
    throughput_rps: float
    error_rate_pct: float
    avg_rtt_ms: float
    min_rtt_ms: float
    max_rtt_ms: float
    p50_rtt_ms: float
    p95_rtt_ms: float
    p99_rtt_ms: float


def calculate_percentile(sorted_values: Sequence[float], percentile: float) -> float:
    """Calculate the nearest-rank percentile on a pre-sorted sequence."""
    if not sorted_values:
        return 0.0
    if percentile <= 0:
        return float(sorted_values[0])
    if percentile >= 100:
        return float(sorted_values[-1])
    idx = math.ceil((percentile / 100.0) * len(sorted_values)) - 1
    idx = max(0, min(idx, len(sorted_values) - 1))
    return float(sorted_values[idx])


def summarize_metrics(
    metrics: Iterable[RequestMetric],
    clients: int,
    requests_per_client: int,
    duration_seconds: float,
) -> BenchmarkSummary:
    all_metrics = list(metrics)
    ok_rtts = sorted(m.rtt_ms for m in all_metrics if m.status == "OK" and m.rtt_ms >= 0)

    total_requests = len(all_metrics)
    success_count = len(ok_rtts)
    error_count = total_requests - success_count

    avg_rtt = statistics.mean(ok_rtts) if ok_rtts else 0.0
    min_rtt = ok_rtts[0] if ok_rtts else 0.0
    max_rtt = ok_rtts[-1] if ok_rtts else 0.0
    p50_rtt = calculate_percentile(ok_rtts, 50.0)
    p95_rtt = calculate_percentile(ok_rtts, 95.0)
    p99_rtt = calculate_percentile(ok_rtts, 99.0)

    throughput = (success_count / duration_seconds) if duration_seconds > 0 else 0.0
    error_rate = (error_count / total_requests * 100.0) if total_requests > 0 else 0.0

    return BenchmarkSummary(
        clients=clients,
        requests_per_client=requests_per_client,
        total_requests=total_requests,
        success_count=success_count,
        error_count=error_count,
        duration_seconds=duration_seconds,
        throughput_rps=throughput,
        error_rate_pct=error_rate,
        avg_rtt_ms=avg_rtt,
        min_rtt_ms=min_rtt,
        max_rtt_ms=max_rtt,
        p50_rtt_ms=p50_rtt,
        p95_rtt_ms=p95_rtt,
        p99_rtt_ms=p99_rtt,
    )


def export_metrics_csv(metrics: Iterable[RequestMetric], output_path: str | Path) -> Path:
    """Write per-request raw benchmark metrics to a UTF-8 CSV file."""
    path = Path(output_path)
    if path.parent and str(path.parent) != ".":
        path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(mode="w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow([
            "client_id",
            "seq",
            "request_id",
            "timestamp",
            "rtt_ms",
            "payload_bytes",
            "status",
            "error_detail",
        ])
        for m in metrics:
            writer.writerow([
                m.client_id,
                m.seq,
                m.request_id,
                f"{m.timestamp:.6f}",
                f"{m.rtt_ms:.4f}" if m.rtt_ms >= 0 else "-1.0000",
                m.payload_bytes,
                m.status,
                m.error_detail,
            ])
    return path
