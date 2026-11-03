import asyncio
import struct

from common.protocol import MAX_FRAME_BYTES, encode_message, read_message
from server.app import EchoServer, ServerConfig


def test_echo_and_client_error_isolation():
    async def scenario():
        app = EchoServer(ServerConfig(port=0, timeout_seconds=0.2, max_payload_bytes=16))
        listener = await app.start()
        port = listener.sockets[0].getsockname()[1]

        async def connect():
            return await asyncio.open_connection("127.0.0.1", port)

        async def close(writer):
            writer.close()
            await writer.wait_closed()

        async def echo(index):
            reader, writer = await connect()
            try:
                message = {"requestId": str(index), "payload": "hello"}
                frame = encode_message(message)
                writer.write(frame[:2])
                await writer.drain()
                await asyncio.sleep(0.001)
                writer.write(frame[2:] + frame)
                await writer.drain()
                assert await read_message(reader, 16) == message
                assert await read_message(reader, 16) == message
            finally:
                await close(writer)

        try:
            await echo(0)
            await asyncio.gather(*(echo(i) for i in range(10)))
            invalid_frames = [
                struct.pack("!I", 0),
                struct.pack("!I", MAX_FRAME_BYTES + 1),
                struct.pack("!I", 1) + b"{",
                struct.pack("!I", 1) + b"\xff",
                encode_message({"requestId": 1, "payload": "x"}),
                encode_message({"requestId": "x", "payload": "a" * 17}),
            ]
            for frame in invalid_frames:
                reader, writer = await connect()
                writer.write(frame)
                await writer.drain()
                assert await asyncio.wait_for(reader.read(), 2) == b""
                await close(writer)
                await echo(99)
            # An incomplete request times out; an abruptly closed client is isolated.
            reader, writer = await connect()
            writer.write(b"\x00")
            await writer.drain()
            assert await asyncio.wait_for(reader.read(), 2) == b""
            await close(writer)
            _, writer = await connect()
            writer.transport.abort()
            await echo(100)
        finally:
            listener.close()
            await listener.wait_closed()
            await app.close_clients()

    asyncio.run(asyncio.wait_for(scenario(), 10))
