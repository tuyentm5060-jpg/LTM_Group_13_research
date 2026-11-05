import asyncio
from .client.client_manager import run_many_clients


def run_generator(host, port, client_count, stop_event, log_callback):
    """Run the asyncio event loop in the GUI worker thread."""
    return asyncio.run(
        run_many_clients(host, port, client_count, stop_event, log_callback)
    )
