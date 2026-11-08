"""Đọc raw data, tổng hợp và vẽ biểu đồ:
   - latency_vs_clients.png   (avg + p95, error bar min–max)
   - throughput_vs_clients.png
   - cpu_vs_clients.png
   - summary.csv, runs_detail.csv
"""

import argparse
import csv
import glob
import json
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_path(raw_path: str | Path):
    p = Path(raw_path)
    if p.is_absolute():
        return p
    root_candidates = [PROJECT_ROOT / p, Path.cwd() / p]
    for candidate in root_candidates:
        if candidate.exists():
            return candidate
    return PROJECT_ROOT / p


def _float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_percent(value):
    num = _float(value)
    if num is None:
        return None
    return num * 100.0 if 0.0 <= num <= 1.0 else num


def _normalize_record(row):
    clients = row.get("clients")
    if clients is None:
        clients = row.get("client_count")
    if clients is None:
        clients = row.get("n_clients")
    if clients is None:
        return None

    rec = {
        "run_id": row.get("run_id") or row.get("id") or row.get("name"),
        "clients": int(float(clients)),
        "avg_latency_ms": _float(row.get("avg_latency_ms") or row.get("latency_mean_ms")),
        "p95_latency_ms": _float(row.get("p95_latency_ms") or row.get("latency_p95_ms")),
        "throughput_req_s": _float(row.get("throughput_req_s") or row.get("throughput_rps")),
        "error_rate_pct": _normalize_percent(row.get("error_rate_pct") or row.get("error_rate")),
        "cpu_avg_pct": _float(row.get("cpu_avg_pct") or row.get("cpu_percent")),
    }
    if rec["avg_latency_ms"] is None and row.get("latency_mean_ms") is not None:
        rec["avg_latency_ms"] = _float(row.get("latency_mean_ms"))
    return rec


def load_benchmark_csv(csv_path: Path):
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            if not raw or not any((v is not None and str(v).strip() != "") for v in raw.values()):
                continue
            rec = _normalize_record(raw)
            if rec is not None:
                rows.append(rec)
    return rows


def load_metas(in_dir: Path):
    rows = []
    for p in sorted(glob.glob(str(in_dir / "meta_*.json"))):
        with open(p, encoding="utf-8") as f:
            rows.append(json.load(f))

    if rows:
        return rows

    csv_candidates = []
    for p in sorted(in_dir.glob("*.csv")):
        if p.name in {"summary.csv", "runs_detail.csv"}:
            continue
        csv_candidates.append(p)

    if not csv_candidates:
        return []

    benchmark_file = csv_candidates[0]
    return load_benchmark_csv(benchmark_file)


def _agg(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return (None, None, None)
    return (statistics.mean(vals), min(vals), max(vals))


def summarize(metas):
    by_clients: dict = {}
    for m in metas:
        by_clients.setdefault(m["clients"], []).append(m)

    summary = []
    for c in sorted(by_clients):
        runs = by_clients[c]

        def g(key):
            return _agg([r.get(key) for r in runs])

        summary.append(
            {
                "clients": c,
                "n_runs": len(runs),
                "avg_latency_ms": g("avg_latency_ms"),
                "p95_latency_ms": g("p95_latency_ms"),
                "throughput_req_s": g("throughput_req_s"),
                "error_rate_pct": g("error_rate_pct"),
                "cpu_avg_pct": g("cpu_avg_pct"),
            }
        )
    return summary


def _err_axis(triple):
    mean, lo, hi = triple
    if mean is None:
        return 0.0, 0.0
    return (mean - lo if lo is not None else 0.0), (hi - mean if hi is not None else 0.0)


def plot_latency(summary, out_path):
    cs = [s["clients"] for s in summary]
    avg = [s["avg_latency_ms"][0] or 0 for s in summary]
    p95 = [s["p95_latency_ms"][0] or 0 for s in summary]
    avg_err = [_err_axis(s["avg_latency_ms"]) for s in summary]
    p95_err = [_err_axis(s["p95_latency_ms"]) for s in summary]

    x = list(range(len(cs)))
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.errorbar(
        x, avg,
        yerr=[[e[0] for e in avg_err], [e[1] for e in avg_err]],
        fmt="o-", capsize=4, label="Avg latency"
    )
    ax.errorbar(
        x, p95,
        yerr=[[e[0] for e in p95_err], [e[1] for e in p95_err]],
        fmt="s--", capsize=4, label="P95 latency"
    )
    ax.set_xticks(x)
    ax.set_xticklabels([str(c) for c in cs])
    ax.set_xlabel("Concurrent clients")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Latency vs. concurrent clients")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_throughput(summary, out_path):
    cs = [s["clients"] for s in summary]
    tp = [s["throughput_req_s"][0] or 0 for s in summary]
    errs = [_err_axis(s["throughput_req_s"]) for s in summary]
    x = list(range(len(cs)))
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.errorbar(
        x, tp,
        yerr=[[e[0] for e in errs], [e[1] for e in errs]],
        fmt="o-", capsize=4, color="tab:green"
    )
    ax.set_xticks(x)
    ax.set_xticklabels([str(c) for c in cs])
    ax.set_xlabel("Concurrent clients")
    ax.set_ylabel("Throughput (req/s)")
    ax.set_title("Throughput vs. concurrent clients")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_cpu(summary, out_path):
    cs = [s["clients"] for s in summary]
    cpu = [s["cpu_avg_pct"][0] or 0 for s in summary]
    errs = [_err_axis(s["cpu_avg_pct"]) for s in summary]
    x = list(range(len(cs)))
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.errorbar(
        x, cpu,
        yerr=[[e[0] for e in errs], [e[1] for e in errs]],
        fmt="o-", capsize=4, color="tab:red"
    )
    ax.set_xticks(x)
    ax.set_xticklabels([str(c) for c in cs])
    ax.set_xlabel("Concurrent clients")
    ax.set_ylabel("Server CPU (% of one core)")
    ax.set_title("Server CPU vs. concurrent clients")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--in-dir", default="experiments/raw-data")
    p.add_argument("--out-dir", default="experiments/figures")
    args = p.parse_args()

    in_dir = _resolve_path(args.in_dir)
    out_dir = _resolve_path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    metas = load_metas(in_dir)
    if not metas:
        print(f"Không tìm thấy dữ liệu đầu vào trong {in_dir}.")
        print("Hãy chạy benchmark trước, ví dụ: python -m src.load_generator.run_load --clients 1 --run-id demo_1 --out-dir experiments/raw-data")
        return 1
    summary = summarize(metas)

    # summary.csv (trung bình + min + max)
    with open(in_dir / "summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "clients", "n_runs",
                "avg_latency_mean", "avg_latency_min", "avg_latency_max",
                "p95_mean", "p95_min", "p95_max",
                "throughput_mean", "throughput_min", "throughput_max",
                "error_rate_mean", "error_rate_min", "error_rate_max",
                "cpu_mean", "cpu_min", "cpu_max",
            ]
        )
        for s in summary:
            row = [s["clients"], s["n_runs"]]
            for key in ["avg_latency_ms", "p95_latency_ms", "throughput_req_s",
                        "error_rate_pct", "cpu_avg_pct"]:
                m, mn, mx = s[key]
                row += [m, mn, mx]
            w.writerow(row)

    # runs_detail.csv (từng lần chạy)
    with open(in_dir / "runs_detail.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["run_id", "clients", "avg_latency_ms", "p95_latency_ms",
             "throughput_req_s", "error_rate_pct", "cpu_avg_pct",
             "total_requests", "successful_requests", "failed_requests"]
        )
        for m in sorted(metas, key=lambda x: (x["clients"], x["run_id"])):
            w.writerow(
                [
                    m["run_id"], m["clients"],
                    m.get("avg_latency_ms"), m.get("p95_latency_ms"),
                    m.get("throughput_req_s"), m.get("error_rate_pct"),
                    m.get("cpu_avg_pct"),
                    m.get("total_requests"), m.get("successful_requests"),
                    m.get("failed_requests"),
                ]
            )

    plot_latency(summary, out_dir / "latency_vs_clients.png")
    plot_throughput(summary, out_dir / "throughput_vs_clients.png")
    plot_cpu(summary, out_dir / "cpu_vs_clients.png")

    print("\n=== SUMMARY ===")
    for s in summary:
        print(s)
    print(f"\nĐã ghi {in_dir/'summary.csv'}, {in_dir/'runs_detail.csv'}")
    print(f"Biểu đồ trong {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())