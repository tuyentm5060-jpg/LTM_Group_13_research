"""Load generator: N Client logic chạy song song, mỗi Client một kết nối TCP riêng.

Đo latency, throughput, error rate và CPU của Server process.
Ghi raw-data ra CSV + meta JSON + per-second aggregates.
"""

import argparse
import asyncio
import csv
import json
import sys
import time
import uuid
from pathlib import Path

import psutil

from src.common.protocol import (
    MAX_PAYLOAD,
    REQUEST_ID_SIZE,
    encode_message,
    percentile,
    read_message,
)


class ResultCollector:
    def __init__(self):
        self.rows = []

    def add(self, row: dict):
        self.rows.append(row)


async def client_worker(
    client_id: int,
    host: str,
    port: int,
    payload: bytes,
    timeout: float,
    stop_event: asyncio.Event,
    collector: ResultCollector,
    throttle_s: float,
    max_retries: int = 10,
):
    """Một Client logic: loop closed-loop gửi/nhận cho đến khi stop_event set."""
    retries = 0
    while not stop_event.is_set():
        try:
            reader, writer = await asyncio.open_connection(host, port, limit=MAX_PAYLOAD * 2)
        except (OSError, ConnectionRefusedError) as exc:
            print(f"[client {client_id}] connect failed: {exc}", file=sys.stderr)
            retries += 1
            if retries >= max_retries:
                print(f"[client {client_id}] giving up after {retries} retries", file=sys.stderr)
                return
            await asyncio.sleep(0.5)
            continue

        retries = 0
        try:
            while not stop_event.is_set():
                request_id = uuid.uuid4().bytes
                message = encode_message(request_id, payload)
                send_t = time.perf_counter()
                try:
                    writer.write(message)
                    await writer.drain()
                    resp_id, resp_payload = await asyncio.wait_for(
                        read_message(reader, len(payload) + 1024), timeout=timeout
                    )
                    recv_t = time.perf_counter()
                    latency_ms = (recv_t - send_t) * 1000.0
                    if resp_id != request_id:
                        status = "mismatch_id"
                    elif resp_payload != payload:
                        status = "mismatch_payload"
                    else:
                        status = "ok"
                    collector.add(
                        {
                            "client_id": client_id,
                            "request_id": request_id.hex(),
                            "send_t": send_t,
                            "recv_t": recv_t,
                            "latency_ms": latency_ms,
                            "status": status,
                        }
                    )
                    if status != "ok":
                        break  # reconnect
                except asyncio.TimeoutError:
                    collector.add(
                        {
                            "client_id": client_id,
                            "request_id": request_id.hex(),
                            "send_t": send_t,
                            "recv_t": time.perf_counter(),
                            "latency_ms": None,
                            "status": "timeout",
                        }
                    )
                    break
                except (ConnectionResetError, BrokenPipeError, OSError, asyncio.IncompleteReadError):
                    collector.add(
                        {
                            "client_id": client_id,
                            "request_id": request_id.hex(),
                            "send_t": send_t,
                            "recv_t": time.perf_counter(),
                            "latency_ms": None,
                            "status": "connection_error",
                        }
                    )
                    break

                if throttle_s > 0:
                    await asyncio.sleep(throttle_s)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass


async def cpu_sampler(pid: int, samples: list, stop_event: asyncio.Event, interval: float = 0.5):
    try:
        proc = psutil.Process(pid)
        proc.cpu_percent(interval=None)  # prime
    except psutil.NoSuchProcess:
        print(f"[load] server pid {pid} không tồn tại, bỏ qua đo CPU", file=sys.stderr)
        return

    while not stop_event.is_set():
        await asyncio.sleep(interval)
        if stop_event.is_set():
            break
        try:
            samples.append((time.perf_counter(), proc.cpu_percent(interval=None)))
        except psutil.NoSuchProcess:
            break


async def _run_async(args):
    payload = b"x" * args.payload_size
    collector = ResultCollector()
    stop_event = asyncio.Event()

    cpu_samples: list = []
    cpu_task = None
    if args.server_pid:
        cpu_task = asyncio.create_task(cpu_sampler(args.server_pid, cpu_samples, stop_event))

    run_start = time.perf_counter()
    clients = [
        asyncio.create_task(
            client_worker(
                i,
                args.host,
                args.port,
                payload,
                args.timeout,
                stop_event,
                collector,
                args.throttle_ms / 1000.0,
            )
        )
        for i in range(args.clients)
    ]

    print(f"[load] {args.clients} clients | warmup {args.warmup}s | measure {args.duration}s")
    await asyncio.sleep(args.warmup)
    warmup_end = time.perf_counter()
    await asyncio.sleep(args.duration)
    measure_end = time.perf_counter()

    stop_event.set()
    await asyncio.gather(*clients, return_exceptions=True)
    if cpu_task is not None:
        await cpu_task

    # ---- Ghi dữ liệu ----
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id

    # 1) Raw requests
    raw_path = out_dir / f"raw_requests_{run_id}.csv"
    with open(raw_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["client_id", "request_id", "send_t_rel", "recv_t_rel", "latency_ms", "status", "in_measurement"]
        )
        for r in collector.rows:
            in_m = 1 if warmup_end <= r["send_t"] <= measure_end else 0
            w.writerow(
                [
                    r["client_id"],
                    r["request_id"],
                    round(r["send_t"] - run_start, 6),
                    round(r["recv_t"] - run_start, 6) if r["recv_t"] else "",
                    round(r["latency_ms"], 4) if r["latency_ms"] is not None else "",
                    r["status"],
                    in_m,
                ]
            )

    # 2) CPU samples
    cpu_path = out_dir / f"cpu_{run_id}.csv"
    with open(cpu_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_rel", "cpu_percent"])
        for t, c in cpu_samples:
            w.writerow([round(t - run_start, 3), round(c, 3)])

    # 3) Lọc measurement window
    in_window = [r for r in collector.rows if warmup_end <= r["send_t"] <= measure_end]
    ok_rows = [r for r in in_window if r["status"] == "ok"]
    err_rows = [r for r in in_window if r["status"] != "ok"]
    latencies = sorted(r["latency_ms"] for r in ok_rows if r["latency_ms"] is not None)

    # 4) Per-second aggregates
    per_second: dict = {}
    for r in in_window:
        sec = int(r["send_t"] - warmup_end)
        bucket = per_second.setdefault(sec, {"ok": 0, "err": 0, "lats": []})
        if r["status"] == "ok" and r["latency_ms"] is not None:
            bucket["ok"] += 1
            bucket["lats"].append(r["latency_ms"])
        else:
            bucket["err"] += 1

    with open(out_dir / f"per_second_{run_id}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["second", "ok", "errors", "avg_latency_ms", "p95_latency_ms"])
        for sec in sorted(per_second):
            b = per_second[sec]
            lats = sorted(b["lats"])
            avg = round(sum(lats) / len(lats), 4) if lats else ""
            p95 = round(percentile(lats, 0.95), 4) if lats else ""
            w.writerow([sec, b["ok"], b["err"], avg, p95])

    # 5) CPU trong measurement window
    cpu_in_window = [c for t, c in cpu_samples if warmup_end <= t <= measure_end]

    # 6) Meta summary
    total = len(in_window)
    summary = {
        "run_id": run_id,
        "clients": args.clients,
        "warmup_s": args.warmup,
        "duration_s": args.duration,
        "payload_size": args.payload_size,
        "throttle_ms": args.throttle_ms,
        "host": args.host,
        "port": args.port,
        "total_requests": total,
        "successful_requests": len(ok_rows),
        "failed_requests": len(err_rows),
        "error_rate_pct": round(100.0 * len(err_rows) / max(1, total), 4),
        "throughput_req_s": round(len(ok_rows) / args.duration, 2),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 4) if latencies else None,
        "p95_latency_ms": round(percentile(latencies, 0.95), 4) if latencies else None,
        "cpu_avg_pct": round(sum(cpu_in_window) / len(cpu_in_window), 3) if cpu_in_window else None,
        "cpu_max_pct": round(max(cpu_in_window), 3) if cpu_in_window else None,
        "num_cpu_samples": len(cpu_in_window),
    }
    with open(out_dir / f"meta_{run_id}.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Load generator cho TCP echo server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--clients", type=int, required=True)
    parser.add_argument("--warmup", type=float, default=5.0)
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--payload-size", type=int, default=1024)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--throttle-ms", type=float, default=0.0)
    parser.add_argument("--server-pid", type=int, default=None)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", default="raw-data")
    args = parser.parse_args()

    if args.payload_size > MAX_PAYLOAD:
        print(f"payload-size vượt MAX_PAYLOAD ({MAX_PAYLOAD})", file=sys.stderr)
        sys.exit(2)

    asyncio.run(_run_async(args))


if __name__ == "__main__":
    main()