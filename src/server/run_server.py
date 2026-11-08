"""TCP Server dùng asyncio, một event loop, mỗi Client là một coroutine task."""

import argparse
import asyncio
import logging
import os
import signal

from src.common.protocol import (
    MAX_PAYLOAD,
    ProtocolError,
    encode_message,
    read_message,
)


class EchoServer:
    def __init__(
        self,
        host: str,
        port: int,
        timeout: float = 5.0,
        max_payload: int = MAX_PAYLOAD,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.max_payload = max_payload
        self._active = 0
        self._total_conns = 0
        self._requests = 0
        self._errors = 0

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        log = logging.getLogger("server")
        self._active += 1
        self._total_conns += 1
        log.info(f"conn open peer={peer} active={self._active}")
        try:
            while True:
                try:
                    request_id, payload = await asyncio.wait_for(
                        read_message(reader, self.max_payload), timeout=self.timeout
                    )
                except asyncio.TimeoutError:
                    log.warning(f"timeout peer={peer}")
                    self._errors += 1
                    break
                except asyncio.IncompleteReadError:
                    log.info(f"peer closed peer={peer}")
                    break
                except ProtocolError as exc:
                    log.warning(f"protocol error peer={peer}: {exc}")
                    self._errors += 1
                    break

                try:
                    writer.write(encode_message(request_id, payload))
                    await writer.drain()
                    self._requests += 1
                except (ConnectionResetError, BrokenPipeError):
                    log.info(f"peer reset during write peer={peer}")
                    break
        except Exception as exc:  # noqa: BLE001
            log.exception(f"unexpected error peer={peer}: {exc}")
            self._errors += 1
        finally:
            self._active -= 1
            log.info(
                f"conn close peer={peer} active={self._active} "
                f"total_req={self._requests} total_err={self._errors}"
            )
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass


async def _main_async(args):
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    server_obj = EchoServer(args.host, args.port, args.timeout, args.max_payload)
    server = await asyncio.start_server(
        server_obj.handle, args.host, args.port, limit=MAX_PAYLOAD * 2
    )
    # Báo cho orchestrator biết server đã sẵn sàng (stdout, không qua logging).
    print(
        f"SERVER_READY pid={os.getpid()} host={args.host} port={args.port}",
        flush=True,
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, sig_name):
            try:
                loop.add_signal_handler(getattr(signal, sig_name), stop.set)
            except NotImplementedError:
                # Windows không hỗ trợ add_signal_handler.
                pass

    async with server:
        await stop.wait()


def main():
    parser = argparse.ArgumentParser(description="Asyncio TCP echo server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--max-payload", type=int, default=MAX_PAYLOAD)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()