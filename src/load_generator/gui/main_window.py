"""Tkinter GUI for configuring concurrent clients, measuring RTT/p95 latency, and exporting CSV."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ..generator import run_generator


class LoadGeneratorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TCP Load Generator & Latency Benchmark")
        self.geometry("960x680")
        self.minsize(780, 540)

        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.running = False

        self.host = tk.StringVar(value="127.0.0.1")
        self.port = tk.StringVar(value="9000")
        self.client_count = tk.StringVar(value="10")
        self.requests_per_client = tk.StringVar(value="100")
        self.payload_size = tk.StringVar(value="1024")
        self.timeout = tk.StringVar(value="5.0")
        self.think_time = tk.StringVar(value="0.0")
        self.output_csv = tk.StringVar(value="experiments/raw-data/raw_metrics.csv")
        self.status = tk.StringVar(value="Ready")
        self.metrics_banner = tk.StringVar(
            value="Avg RTT: -- ms | p95 Latency: -- ms | Throughput: -- req/s | Error Rate: -- %"
        )

        self._build()
        self.after(100, self._poll_events)

    def _build(self):
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer, text="TCP LOAD GENERATOR & BENCHMARK",
            font=("Segoe UI", 17, "bold")
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text="Concurrent asyncio TCP clients with RTT, p95 latency, throughput & CSV export"
        ).pack(anchor="w", pady=(2, 12))

        config = ttk.LabelFrame(outer, text="Benchmark configuration", padding=10)
        config.pack(fill="x")

        # Row 0-1: Network & Client load parameters
        ttk.Label(config, text="Server IP / Host").grid(row=0, column=0, sticky="w")
        ttk.Entry(config, textvariable=self.host, width=18).grid(
            row=1, column=0, padx=(0, 10), pady=(0, 8), sticky="ew"
        )

        ttk.Label(config, text="Server Port").grid(row=0, column=1, sticky="w")
        ttk.Entry(config, textvariable=self.port, width=9).grid(
            row=1, column=1, padx=(0, 10), pady=(0, 8), sticky="ew"
        )

        ttk.Label(config, text="Clients (N)").grid(row=0, column=2, sticky="w")
        ttk.Entry(config, textvariable=self.client_count, width=10).grid(
            row=1, column=2, padx=(0, 10), pady=(0, 8), sticky="ew"
        )

        ttk.Label(config, text="Requests / Client").grid(row=0, column=3, sticky="w")
        ttk.Entry(config, textvariable=self.requests_per_client, width=13).grid(
            row=1, column=3, padx=(0, 10), pady=(0, 8), sticky="ew"
        )

        self.start_button = ttk.Button(config, text="Start", command=self.start)
        self.start_button.grid(row=1, column=4, padx=(4, 6), pady=(0, 8))
        self.stop_button = ttk.Button(
            config, text="Stop", command=self.stop, state="disabled"
        )
        self.stop_button.grid(row=1, column=5, pady=(0, 8))

        # Row 2-3: Payload, Timeout, Think-time & CSV output
        ttk.Label(config, text="Payload (bytes)").grid(row=2, column=0, sticky="w")
        ttk.Entry(config, textvariable=self.payload_size, width=14).grid(
            row=3, column=0, padx=(0, 10), sticky="ew"
        )

        ttk.Label(config, text="Timeout (s)").grid(row=2, column=1, sticky="w")
        ttk.Entry(config, textvariable=self.timeout, width=9).grid(
            row=3, column=1, padx=(0, 10), sticky="ew"
        )

        ttk.Label(config, text="Think Time (s)").grid(row=2, column=2, sticky="w")
        ttk.Entry(config, textvariable=self.think_time, width=10).grid(
            row=3, column=2, padx=(0, 10), sticky="ew"
        )

        ttk.Label(config, text="Raw CSV Output Path").grid(row=2, column=3, columnspan=3, sticky="w")
        ttk.Entry(config, textvariable=self.output_csv, width=32).grid(
            row=3, column=3, columnspan=3, sticky="ew"
        )

        summary_frame = ttk.LabelFrame(outer, text="Latest benchmark metrics", padding=8)
        summary_frame.pack(fill="x", pady=(10, 8))
        ttk.Label(
            summary_frame,
            textvariable=self.metrics_banner,
            font=("Consolas", 10, "bold")
        ).pack(anchor="w")

        status_row = ttk.Frame(outer)
        status_row.pack(fill="x", pady=(0, 6))
        ttk.Label(status_row, text="Status:").pack(side="left")
        ttk.Label(status_row, textvariable=self.status).pack(side="left", padx=6)

        log_frame = ttk.LabelFrame(outer, text="Client activity & summary", padding=8)
        log_frame.pack(fill="both", expand=True)

        self.log = tk.Text(log_frame, wrap="word", font=("Consolas", 9), state="disabled")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        ttk.Button(outer, text="Clear log", command=self.clear_log).pack(
            anchor="w", pady=(8, 0)
        )

    def _write_log(self, message: str):
        self.events.put(("log", message))

    def start(self):
        if self.running:
            return
        host = self.host.get().strip()
        csv_path = self.output_csv.get().strip() or None
        try:
            port = int(self.port.get())
            count = int(self.client_count.get())
            reqs = int(self.requests_per_client.get())
            payload_sz = int(self.payload_size.get())
            timeout_val = float(self.timeout.get())
            think_val = float(self.think_time.get())

            if not host:
                raise ValueError("Server IP/Host cannot be empty.")
            if not 1 <= port <= 65535:
                raise ValueError("Port must be between 1 and 65535.")
            if not 1 <= count <= 10000:
                raise ValueError("Client count must be between 1 and 10000.")
            if reqs < 1:
                raise ValueError("Requests per client must be >= 1.")
            if not 0 <= payload_sz <= 65536:
                raise ValueError("Payload size must be between 0 and 65536 bytes.")
            if timeout_val <= 0:
                raise ValueError("Timeout must be > 0.")
            if think_val < 0:
                raise ValueError("Think time must be >= 0.")
        except ValueError as exc:
            messagebox.showerror("Invalid configuration", str(exc))
            return

        self.running = True
        self.stop_event.clear()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set("Running")
        self._write_log(
            f"=== START host={host}:{port}, clients={count}, reqs/client={reqs}, "
            f"payload={payload_sz}B, timeout={timeout_val}s, think_time={think_val}s ==="
        )

        self.worker = threading.Thread(
            target=self._run_worker,
            args=(host, port, count, reqs, payload_sz, timeout_val, think_val, csv_path),
            daemon=True,
        )
        self.worker.start()

    def _run_worker(self, host, port, count, reqs, payload_sz, timeout_val, think_val, csv_path):
        try:
            results, summary = run_generator(
                host=host,
                port=port,
                client_count=count,
                stop_event=self.stop_event,
                log_callback=self._write_log,
                requests_per_client=reqs,
                payload_size=payload_sz,
                timeout=timeout_val,
                think_time=think_val,
                output_csv=csv_path,
                return_summary=True,
            )
            success = sum(item.status == "SUCCESS" for item in results)
            failed = sum(item.status == "FAILED" for item in results)
            stopped = sum(item.status == "STOPPED" for item in results)
            banner_txt = (
                f"Avg RTT: {summary.avg_rtt_ms:.3f} ms | "
                f"p95 Latency: {summary.p95_rtt_ms:.3f} ms | "
                f"Throughput: {summary.throughput_rps:.2f} req/s | "
                f"Error Rate: {summary.error_rate_pct:.2f} %"
            )
            self.events.put(("metrics", banner_txt))
            self.events.put((
                "finished",
                f"Completed clients: SUCCESS={success}, FAILED={failed}, STOPPED={stopped}"
            ))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def stop(self):
        self.stop_event.set()
        self.status.set("Stopping...")
        self.stop_button.configure(state="disabled")
        self._write_log("Stop requested.")

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _poll_events(self):
        try:
            while True:
                kind, message = self.events.get_nowait()
                if kind == "log":
                    self.log.configure(state="normal")
                    self.log.insert("end", message + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                elif kind == "metrics":
                    self.metrics_banner.set(message)
                elif kind == "finished":
                    self.log.configure(state="normal")
                    self.log.insert("end", message + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                    self.status.set("Completed")
                    self._set_idle()
                elif kind == "error":
                    self.log.configure(state="normal")
                    self.log.insert("end", "ERROR: " + message + "\n")
                    self.log.configure(state="disabled")
                    self.status.set("Error")
                    self._set_idle()
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _set_idle(self):
        self.running = False
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
