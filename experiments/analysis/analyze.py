"""Summarize one raw request CSV and plot RTT using matplotlib."""

import argparse
import csv
import math
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[2]


def read_requests(path):
    """Read the existing load generator format; reject invalid numeric data."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"client_id", "rtt_ms", "payload_bytes", "status"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")
        rows = []
        for line, row in enumerate(reader, start=2):
            try:
                client = int(row["client_id"])
                rtt = float(row["rtt_ms"])
                payload = int(row["payload_bytes"])
                status = row["status"].strip()
                if (client < 1 or payload < 0 or not status
                        or not math.isfinite(rtt) or (status == "OK" and rtt < 0)):
                    raise ValueError("invalid client, payload, status or RTT")
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError(f"Invalid CSV data at line {line}: {exc}") from exc
            rows.append({"client_id": client, "rtt_ms": rtt,
                         "payload_bytes": payload, "status": status})
    if not rows:
        raise ValueError("CSV has no request records")
    return rows


def summarize(rows):
    """Calculate statistics independently of the load generator."""
    rtts = sorted(row["rtt_ms"] for row in rows if row["status"] == "OK")
    total = len(rows)
    success = len(rtts)

    def percentile(percent):
        return rtts[math.ceil(len(rtts) * percent / 100) - 1] if rtts else None

    return {
        "total_requests": total,
        "success_count": success,
        "error_count": total - success,
        "error_rate_pct": (total - success) / total * 100,
        "avg_rtt_ms": statistics.mean(rtts) if rtts else None,
        "min_rtt_ms": rtts[0] if rtts else None,
        "max_rtt_ms": rtts[-1] if rtts else None,
        "p50_rtt_ms": percentile(50),
        "p95_rtt_ms": percentile(95),
        "p99_rtt_ms": percentile(99),
    }


def write_summary(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_results(rows, by_client, summary, output_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.facecolor": "white"})
    blue, orange = "#245B88", "#D97832"
    successful = [row["rtt_ms"] for row in rows if row["status"] == "OK"]
    payloads = ", ".join(str(n) for n in sorted({r["payload_bytes"] for r in rows}))
    caption = (f"{len(rows):,} records | {summary['success_count']:,} successful | "
               f"payload: {payloads} bytes | successful RTTs only")

    fig, ax = plt.subplots(figsize=(11, 5.6), layout="constrained")
    positions = list(range(len(by_client)))
    averages = [r["avg_rtt_ms"] if r["avg_rtt_ms"] is not None else math.nan for r in by_client]
    p95s = [r["p95_rtt_ms"] if r["p95_rtt_ms"] is not None else math.nan for r in by_client]
    ax.bar([x - 0.2 for x in positions], averages, width=0.38, color=blue, label="Average RTT")
    ax.bar([x + 0.2 for x in positions], p95s, width=0.38, color=orange, label="p95 RTT")
    step = max(1, math.ceil(len(positions) / 20))
    ticks = positions[::step]
    ax.set_xticks(ticks, [str(by_client[i]["client_id"]) for i in ticks])
    ax.set(xlabel="Client ID", ylabel="RTT (ms)", title="Response latency by client", ylim=(0, None))
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False)
    if not successful:
        ax.text(0.5, 0.5, "No successful requests", transform=ax.transAxes, ha="center")
    fig.suptitle(caption, fontsize=10, color="#555555")
    fig.savefig(output_dir / "rtt_by_client.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 5.6), layout="constrained")
    if successful:
        ax.hist(successful, bins=min(40, max(5, int(math.sqrt(len(successful))))),
                color=blue, edgecolor="white")
        ax.axvline(summary["avg_rtt_ms"], color="#263640", linewidth=2,
                   label=f"Average: {summary['avg_rtt_ms']:.3f} ms")
        ax.axvline(summary["p95_rtt_ms"], color=orange, linewidth=2, linestyle="--",
                   label=f"p95: {summary['p95_rtt_ms']:.3f} ms")
        ax.legend(frameon=False)
    else:
        ax.text(0.5, 0.5, "No successful requests", transform=ax.transAxes, ha="center")
    ax.set(xlabel="RTT (ms)", ylabel="Successful requests", title="Distribution of response latency")
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)
    fig.suptitle(caption, fontsize=10, color="#555555")
    fig.savefig(output_dir / "rtt_distribution.png", dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Raw request CSV exported by GUI/CLI")
    parser.add_argument("--summary-dir", type=Path, default=ROOT / "experiments/analysis")
    parser.add_argument("--figures-dir", type=Path, default=ROOT / "experiments/figures")
    parser.add_argument("--duration-seconds", type=float,
                        help="Actual measured duration from the SAME benchmark run; optional")
    args = parser.parse_args()
    if args.duration_seconds is not None:
        if not math.isfinite(args.duration_seconds) or args.duration_seconds <= 0:
            parser.error("--duration-seconds must be positive and finite")

    source = args.input
    if source is None:
        candidates = [ROOT / "experiments/raw-data/raw_metrics.csv",
                      ROOT / "src/experiments/raw-data/raw_metrics.csv"]
        source = next((path for path in candidates if path.is_file()), None)
        if source is None:
            parser.error("No raw_metrics.csv found. Export a CSV first or pass --input PATH.")
    if not source.is_file():
        parser.error(f"CSV not found: {source}")
    try:
        rows = read_requests(source)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    summary = summarize(rows)
    clients = sorted({row["client_id"] for row in rows})
    by_client = [dict(client_id=client,
                      **summarize([r for r in rows if r["client_id"] == client]))
                 for client in clients]
    try:
        source_label = str(source.resolve().relative_to(ROOT))
    except ValueError:
        source_label = str(source.resolve())
    overall = dict(source=source_label, clients=len(clients), **summary,
                   duration_seconds=args.duration_seconds,
                   throughput_rps=(summary["success_count"] / args.duration_seconds
                                   if args.duration_seconds is not None else None))
    try:
        import matplotlib  # Check dependency before writing output files.
    except ImportError:
        parser.error("Install matplotlib: python -m pip install matplotlib==3.10.8")
    write_summary(args.summary_dir / "summary.csv", [overall])
    write_summary(args.summary_dir / "by_client.csv", by_client)
    plot_results(rows, by_client, summary, args.figures_dir)
    print(f"Input: {source}")
    print(f"Clients: {len(clients)} | Records: {len(rows)} | "
          f"OK: {summary['success_count']} | Errors: {summary['error_count']}")
    print(f"Summary: {args.summary_dir / 'summary.csv'}")
    print(f"Per client: {args.summary_dir / 'by_client.csv'}")
    print(f"Figures: {args.figures_dir / 'rtt_by_client.png'}, "
          f"{args.figures_dir / 'rtt_distribution.png'}")
    if args.duration_seconds is None:
        print("Throughput left blank: raw CSV does not contain actual benchmark duration.")


if __name__ == "__main__":
    main()
