import asyncio
from client.tcp_client import run_client


async def run_many_clients(host, port, client_count, stop_event, log_callback):
    tasks = [
        asyncio.create_task(run_client(i + 1, host, port, stop_event))
        for i in range(client_count)
    ]

    results = []
    for task in asyncio.as_completed(tasks):
        result = await task
        results.append(result)
        log_callback(
            f"Client {result.client_id:03d} | {result.status} | "
            f"requestId={result.request_id} | {result.detail}"
        )
    return results
