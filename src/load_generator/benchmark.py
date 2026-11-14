"""Command-line benchmark runner for the asyncio TCP load generator."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

# Allow running directly via `python src/load_generator/benchmark.py` without PYTHONPATH=src
_SRC_DIR = Path(__file__).resolve().parents[1]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from load_generator.client.client_manager import run_many_clients
from load_generator.metrics import BenchmarkSummary


def print_summary_table(summary: BenchmarkSummary, output_csv: str | None) -> None:
    print("\n" + "=" * 60)
    print(f"BENCHMARK SUMMARY ({summary.clients} CLIENTS)")
    print("=" * 60)
    print(f"Total requests        : {summary.total_requests} (OK: {summary.success_count} | Error: {summary.error_count})")
    print(f"Elapsed duration      : {summary.duration_seconds:.3f} s")
    print(f"Throughput            : {summary.throughput_rps:.2f} req/s")
    print(f"Error rate            : {summary.error_rate_pct:.2f} %")
    print(f"RTT min / avg / max   : {summary.min_rtt_ms:.3f} / {summary.avg_rtt_ms:.3f} / {summary.max_rtt_ms:.3f} ms")
    print(f"p50 Latency           : {summary.p50_rtt_ms:.3f} ms")
    print(f"p95 Latency           : {summary.p95_rtt_ms:.3f} ms")
    print(f"p99 Latency           : {summary.p99_rtt_ms:.3f} ms")
    if output_csv:
        print(f"Raw CSV output        : {output_csv}")
    print("=" * 60 + "\n")


async def _run_single_cli(args: argparse.Namespace) -> None:
    stop_event = asyncio.Event()
    log_fn = print if args.verbose else None
    _, summary = await run_many_clients(
        host=args.host,
        port=args.port,
        client_count=args.clients,
        stop_event=stop_event,
        log_callback=log_fn,
        requests_per_client=args.requests,
        payload_size=args.payload_size,
        connect_timeout=args.timeout,
        response_timeout=args.timeout,
        think_time=args.think_time,
        warmup_seconds=args.warmup,
        measurement_seconds=args.duration,
        output_csv=args.output,
        return_summary=True,
    )
    print_summary_table(summary, args.output)


async def _run_config_cli(args: argparse.Namespace) -> None:
    cfg_path = Path(args.config)
    with cfg_path.open("r", encoding="utf-8") as fp:
        cfg = json.load(fp)

    host = args.host if args.host != "127.0.0.1" else cfg.get("host", "127.0.0.1")
    port = args.port if args.port != 9000 else cfg.get("port", 9000)
    client_counts = cfg.get("client_counts", [1, 10, 50])
    repetitions = int(cfg.get("repetitions", 1))
    payload_size = int(cfg.get("payload_bytes", args.payload_size))
    warmup_seconds = float(cfg.get("warmup_seconds", 0.0))
    measurement_seconds = float(cfg.get("measurement_seconds", 0.0))
    timeout = float(cfg.get("timeout_seconds", args.timeout))

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stop_event = asyncio.Event()

    for c_count in client_counts:
        for rep in range(1, repetitions + 1):
            csv_file = out_dir / f"raw_{c_count}c_rep{rep}.csv"
            print(f">>> Running {c_count} clients (repetition {rep}/{repetitions})...")
            _, summary = await run_many_clients(
                host=host,
                port=port,
                client_count=int(c_count),
                stop_event=stop_event,
                log_callback=print if args.verbose else None,
                requests_per_client=args.requests,
                payload_size=payload_size,
                connect_timeout=timeout,
                response_timeout=timeout,
                think_time=args.think_time,
                warmup_seconds=warmup_seconds,
                measurement_seconds=measurement_seconds,
                output_csv=csv_file,
                return_summary=True,
            )
            print_summary_table(summary, str(csv_file))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Asyncio TCP Load Generator & Latency Benchmark CLI")
    parser.add_argument("--cli", action="store_true", help="Run in headless CLI mode")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="TCP server IP/hostname")
    parser.add_argument("--port", type=int, default=9000, help="TCP server port (default: 9000)")
    parser.add_argument("-c", "--clients", type=int, default=1, help="Number of concurrent clients (e.g., 1, 10, 50)")
    parser.add_argument("-n", "--requests", type=int, default=100, help="Requests per client when --duration is 0")
    parser.add_argument("-s", "--payload-size", type=int, default=1024, help="Payload size in UTF-8 bytes")
    parser.add_argument("-t", "--timeout", type=float, default=5.0, help="Connect/response timeout in seconds")
    parser.add_argument("--think-time", type=float, default=0.0, help="Delay between requests in seconds (0 = closed-loop)")
    parser.add_argument("--warmup", type=float, default=0.0, help="Warm-up duration in seconds before recording")
    parser.add_argument("--duration", type=float, default=0.0, help="Measurement duration in seconds (overrides -n if > 0)")
    parser.add_argument("-o", "--output", type=str, default="experiments/raw-data/raw_metrics.csv", help="Output raw CSV file path")
    parser.add_argument("--config", type=str, default=None, help="Path to JSON experiment config (e.g., experiments/configs/baseline.json)")
    parser.add_argument("--output-dir", type=str, default="experiments/raw-data", help="Output directory when running with --config")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print per-client completion logs")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.config:
            asyncio.run(_run_config_cli(args))
        else:
            asyncio.run(_run_single_cli(args))
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user.")


if __name__ == "__main__":
    main()
