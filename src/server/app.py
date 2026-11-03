"""Asynchronous TCP echo server; one coroutine per connection."""

import asyncio
from dataclasses import dataclass
import logging
import math

from common.protocol import ProtocolError, encode_message, read_message

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 9000
    timeout_seconds: float = 5.0
    max_payload_bytes: int = 65536

    def __post_init__(self):
        if not 0 <= self.port <= 65535:
            raise ValueError("port must be between 0 and 65535")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout must be positive and finite")
        if not 1 <= self.max_payload_bytes <= 65536:
            raise ValueError("max payload must be between 1 and 65536 bytes")


class EchoServer:
    def __init__(self, config: ServerConfig):
        self.config = config
        self._tasks: set[asyncio.Task] = set()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        task = asyncio.current_task()
        self._tasks.add(task)
        peer = writer.get_extra_info("peername")
        try:
            while True:
                async with asyncio.timeout(self.config.timeout_seconds):
                    message = await read_message(reader, self.config.max_payload_bytes)
                writer.write(encode_message(message))
                async with asyncio.timeout(self.config.timeout_seconds):
                    await writer.drain()
        except asyncio.IncompleteReadError:
            LOGGER.debug("Client disconnected: %s", peer)
        except (ProtocolError, TimeoutError, ConnectionError, OSError) as exc:
            LOGGER.debug("Closing client %s: %s", peer, exc)
        finally:
            writer.close()
            try:
                async with asyncio.timeout(self.config.timeout_seconds):
                    await writer.wait_closed()
            except (TimeoutError, ConnectionError, OSError):
                pass
            finally:
                self._tasks.discard(task)

    async def start(self) -> asyncio.Server:
        return await asyncio.start_server(self.handle_client, self.config.host, self.config.port)

    async def close_clients(self):
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def serve(config: ServerConfig):
    app = EchoServer(config)
    server = await app.start()
    LOGGER.info("Listening on %s", [sock.getsockname() for sock in server.sockets])
    try:
        async with server:
            await server.serve_forever()
    finally:
        await app.close_clients()
