import importlib.util
from pathlib import Path


def load_analyze_module():
    module_path = Path(__file__).resolve().parents[1] / "experiments" / "analysis" / "analyze.py"
    spec = importlib.util.spec_from_file_location("analyze_script", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_benchmark_csv(tmp_path):
    csv_path = tmp_path / "benchmark_results.csv"
    csv_path.write_text(
        "run_id,client_count,successful_requests,failed_requests,throughput_rps,latency_mean_ms,latency_p95_ms,error_rate,cpu_percent\n"
        "run_1,1,100,0,50,10.0,25.0,0.0,15.0\n"
        "run_2,1,120,2,60,12.0,28.0,1.5,16.0\n",
        encoding="utf-8",
    )

    mod = load_analyze_module()
    rows = mod.load_benchmark_csv(csv_path)

    assert rows[0]["clients"] == 1
    assert rows[0]["avg_latency_ms"] == 10.0
    assert rows[0]["throughput_req_s"] == 50.0
    assert rows[0]["error_rate_pct"] == 0.0
