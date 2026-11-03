"""Check local dependencies without starting a network experiment."""

import importlib.metadata
import json
from pathlib import Path
import sys


def main() -> int:
    print(f"Python: {sys.version.split()[0]}")
    print(f"Interpreter: {sys.executable}")
    failures = []
    if sys.version_info < (3, 11):
        failures.append("Python >= 3.11 required")
    if sys.prefix == sys.base_prefix:
        failures.append("Use the project .venv interpreter")
    for package in ("psutil", "matplotlib", "pytest"):
        try:
            print(f"{package}: {importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            failures.append(f"Missing dependency: {package}")
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "experiments/configs/baseline.json").read_text())
    print(f"Baseline: {config['client_counts']}, {config['repetitions']} repetitions")
    for failure in failures:
        print(f"ERROR: {failure}", file=sys.stderr)
    if not failures:
        print("Environment OK. Benchmark implementation is still pending.")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
