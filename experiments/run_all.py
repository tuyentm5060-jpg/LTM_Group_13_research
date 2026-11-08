"""Chạy toàn bộ thực nghiệm:
   - Start TCP server subprocess
   - Với mỗi mức Client (1, 10, 50) chạy 3 lần
   - Stop server
   - Dữ liệu thô lưu vào raw-data/
"""

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def wait_for_port(host: str, port: int, timeout: float = 15.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=9000)
    p.add_argument("--clients", nargs="+", type=int, default=[1, 10, 50])
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--warmup", type=float, default=5.0)
    p.add_argument("--duration", type=float, default=20.0)
    p.add_argument("--payload-size", type=int, default=1024)
    p.add_argument("--throttle-ms", type=float, default=0.0)
    p.add_argument("--out-dir", default="raw-data")
    p.add_argument("--pause-between-runs", type=float, default=1.0)
    args = p.parse_args()

    out_dir = Path(PROJECT_ROOT) / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    py = sys.executable
    server_log_path = out_dir / "server.log"
    server_log = open(server_log_path, "w")

    print("[orchestrator] starting server subprocess...")
    server_proc = subprocess.Popen(
        [py, "-m", "src.server.run_server", "--host", args.host, "--port", str(args.port)],
        cwd=str(PROJECT_ROOT),
        stdout=server_log,
        stderr=subprocess.STDOUT,
    )
    rc = 0
    try:
        if not wait_for_port(args.host, args.port, timeout=15.0):
            print("[orchestrator] server không sẵn sàng", file=sys.stderr)
            return 1
        print(f"[orchestrator] server pid={server_proc.pid}")

        for n_clients in args.clients:
            for rep in range(1, args.repeats + 1):
                run_id = f"c{n_clients}_r{rep}"
                print(f"[orchestrator] running {run_id} ...")
                cmd = [
                    py, "-m", "src.load_generator.run_load",
                    "--host", args.host,
                    "--port", str(args.port),
                    "--clients", str(n_clients),
                    "--warmup", str(args.warmup),
                    "--duration", str(args.duration),
                    "--payload-size", str(args.payload_size),
                    "--throttle-ms", str(args.throttle_ms),
                    "--server-pid", str(server_proc.pid),
                    "--run-id", run_id,
                    "--out-dir", str(out_dir),
                ]
                subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)
                time.sleep(args.pause_between_runs)
    except subprocess.CalledProcessError as exc:
        print(f"[orchestrator] run failed: {exc}", file=sys.stderr)
        rc = exc.returncode
    finally:
        print("[orchestrator] stopping server...")
        try:
            server_proc.terminate()
            server_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server_proc.kill()
        server_log.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())