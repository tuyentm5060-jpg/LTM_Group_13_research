import asyncio
import csv
from pathlib import Path

from load_generator.client.client_manager import run_many_clients
from load_generator.metrics import calculate_percentile
from server.app import EchoServer, ServerConfig


def test_percentile_calculation():
    data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    assert calculate_percentile(data, 50) == 5.0
    assert calculate_percentile(data, 95) == 10.0
    assert calculate_percentile([], 95) == 0.0


def test_load_generator_integration_and_csv_export(tmp_path: Path):
    async def scenario():
        server = EchoServer(ServerConfig(host="127.0.0.1", port=0, timeout_seconds=5.0, max_payload_bytes=65536))
        listener = await server.start()
        port = listener.sockets[0].getsockname()[1]

        try:
            for clients in (1, 10, 50):
                reqs_per_client = 5
                csv_out = tmp_path / f"raw_initial_{clients}c.csv"
                results, summary = await run_many_clients(
                    host="127.0.0.1",
                    port=port,
                    client_count=clients,
                    requests_per_client=reqs_per_client,
                    payload_size=1024,
                    output_csv=csv_out,
                    return_summary=True,
                )

                expected_total = clients * reqs_per_client
                assert len(results) == clients
                assert summary.total_requests == expected_total
                assert summary.success_count == expected_total
                assert summary.error_count == 0
                assert summary.error_rate_pct == 0.0
                assert summary.avg_rtt_ms > 0.0
                assert summary.p95_rtt_ms >= summary.p50_rtt_ms
                assert summary.throughput_rps > 0.0

                assert csv_out.exists()
                with csv_out.open("r", encoding="utf-8") as fp:
                    rows = list(csv.DictReader(fp))
                assert len(rows) == expected_total
                assert all(r["status"] == "OK" for r in rows)
                assert all(int(r["payload_bytes"]) == 1024 for r in rows)
        finally:
            listener.close()
            await listener.wait_closed()
            await server.close_clients()

    asyncio.run(asyncio.wait_for(scenario(), 15))
