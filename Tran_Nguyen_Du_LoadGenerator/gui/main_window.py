import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from load_generator.generator import run_generator


class LoadGeneratorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TCP Load Generator")
        self.geometry("900x620")
        self.minsize(720, 480)

        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.running = False

        self.host = tk.StringVar(value="127.0.0.1")
        self.port = tk.StringVar(value="9000")
        self.client_count = tk.StringVar(value="10")
        self.status = tk.StringVar(value="Ready")

        self._build()
        self.after(100, self._poll_events)

    def _build(self):
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer, text="TCP LOAD GENERATOR",
            font=("Segoe UI", 17, "bold")
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text="Concurrent TCP clients using Python asyncio"
        ).pack(anchor="w", pady=(2, 14))

        config = ttk.LabelFrame(outer, text="Connection settings", padding=10)
        config.pack(fill="x")

        ttk.Label(config, text="Server IP / Host").grid(row=0, column=0, sticky="w")
        ttk.Entry(config, textvariable=self.host, width=22).grid(
            row=1, column=0, padx=(0, 12), sticky="ew"
        )

        ttk.Label(config, text="Server Port").grid(row=0, column=1, sticky="w")
        ttk.Entry(config, textvariable=self.port, width=10).grid(
            row=1, column=1, padx=(0, 12), sticky="ew"
        )

        ttk.Label(config, text="Number of Clients").grid(row=0, column=2, sticky="w")
        ttk.Entry(config, textvariable=self.client_count, width=12).grid(
            row=1, column=2, padx=(0, 12), sticky="ew"
        )

        self.start_button = ttk.Button(config, text="Start", command=self.start)
        self.start_button.grid(row=1, column=3, padx=(0, 6))
        self.stop_button = ttk.Button(
            config, text="Stop", command=self.stop, state="disabled"
        )
        self.stop_button.grid(row=1, column=4)

        ttk.Label(
            outer,
            text="Each client sends one JSON request: requestId + payload (1024 bytes).",
            wraplength=850
        ).pack(anchor="w", pady=12)

        status_row = ttk.Frame(outer)
        status_row.pack(fill="x", pady=(0, 8))
        ttk.Label(status_row, text="Status:").pack(side="left")
        ttk.Label(status_row, textvariable=self.status).pack(side="left", padx=6)

        log_frame = ttk.LabelFrame(outer, text="Client activity", padding=8)
        log_frame.pack(fill="both", expand=True)

        self.log = tk.Text(log_frame, wrap="word", font=("Consolas", 9), state="disabled")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        ttk.Button(outer, text="Clear log", command=self.clear_log).pack(
            anchor="w", pady=(8, 0)
        )

    def _write_log(self, message):
        self.events.put(("log", message))

    def start(self):
        if self.running:
            return
        host = self.host.get().strip()
        try:
            port = int(self.port.get())
            count = int(self.client_count.get())
            if not host:
                raise ValueError("Server IP/Host cannot be empty.")
            if not 1 <= port <= 65535:
                raise ValueError("Port must be between 1 and 65535.")
            if not 1 <= count <= 10000:
                raise ValueError("Client count must be between 1 and 10000.")
        except ValueError as exc:
            messagebox.showerror("Invalid configuration", str(exc))
            return

        self.running = True
        self.stop_event.clear()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set("Running")
        self._write_log(
            f"=== START host={host}:{port}, clients={count}, payload=1024 bytes ==="
        )

        self.worker = threading.Thread(
            target=self._run_worker, args=(host, port, count), daemon=True
        )
        self.worker.start()

    def _run_worker(self, host, port, count):
        try:
            results = run_generator(
                host, port, count, self.stop_event, self._write_log
            )
            success = sum(item.status == "SUCCESS" for item in results)
            failed = sum(item.status == "FAILED" for item in results)
            stopped = sum(item.status == "STOPPED" for item in results)
            sent = sum(item.status == "SENT" for item in results)
            self.events.put((
                "finished",
                f"Completed: SUCCESS={success}, SENT={sent}, "
                f"FAILED={failed}, STOPPED={stopped}"
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
