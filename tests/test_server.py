import asyncio
import socket
import struct

import pytest

from src.common.protocol import MAX_PAYLOAD, REQUEST_ID_SIZE, encode_message, read_message
from src.server.run_server import EchoServer


@pytest.fixture
def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _run(coro):
    return asyncio.run(coro)


def test_echo_single_client(free_port):
    async def _go():
        srv = EchoServer("127.0.0.1", free_port)
        server = await asyncio.start_server(srv.handle, "127.0.0.1", free_port)
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", free_port)
            try:
                rid = b"A" * REQUEST_ID_SIZE
                payload = b"hello"
                writer.write(encode_message(rid, payload))
                await writer.drain()
                r, p = await read_message(reader)
                assert r == rid
                assert p == payload
            finally:
                writer.close()
                await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()

    _run(_go())


def test_multiple_clients(free_port):
    async def _go():
        srv = EchoServer("127.0.0.1", free_port)
        server = await asyncio.start_server(srv.handle, "127.0.0.1", free_port)
        try:
            async def one(i):
                reader, writer = await asyncio.open_connection("127.0.0.1", free_port)
                try:
                    rid = bytes([i]) * REQUEST_ID_SIZE
                    payload = f"msg-{i}".encode()
                    writer.write(encode_message(rid, payload))
                    await writer.drain()
                    r, p = await read_message(reader)
                    assert r == rid
                    assert p == payload
                finally:
                    writer.close()
                    await writer.wait_closed()

            await asyncio.gather(*[one(i) for i in range(8)])
        finally:
            server.close()
            await server.wait_closed()

    _run(_go())


def test_bad_client_does_not_kill_server(free_port):
    async def _go():
        srv = EchoServer("127.0.0.1", free_port)
        server = await asyncio.start_server(srv.handle, "127.0.0.1", free_port)
        try:
            # Client xấu: gửi header length = 4 (< REQUEST_ID_SIZE), rồi đóng
            bad_reader, bad_writer = await asyncio.open_connection("127.0.0.1", free_port)
            bad_writer.write(struct.pack(">I", 4) + b"xxxx")
            await bad_writer.drain()
            bad_writer.close()
            await bad_writer.wait_closed()
            await asyncio.sleep(0.15)

            # Client tốt vẫn phải hoạt động
            reader, writer = await asyncio.open_connection("127.0.0.1", free_port)
            try:
                rid = b"C" * REQUEST_ID_SIZE
                payload = b"after-bad"
                writer.write(encode_message(rid, payload))
                await writer.drain()
                r, p = await read_message(reader)
                assert r == rid
                assert p == payload
            finally:
                writer.close()
                await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()

    _run(_go())


def test_payload_oversize_connection_closed(free_port):
    async def _go():
        srv = EchoServer("127.0.0.1", free_port, max_payload=1024)
        server = await asyncio.start_server(srv.handle, "127.0.0.1", free_port)
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", free_port)
            try:
                rid = b"D" * REQUEST_ID_SIZE
                body_len = REQUEST_ID_SIZE + 5000
                writer.write(struct.pack(">I", body_len) + rid + b"x" * 5000)
                await writer.drain()
                data = await asyncio.wait_for(reader.read(100), timeout=2.0)
                assert data == b""  # EOF — server đã đóng kết nối
            finally:
                writer.close()
                await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()

    _run(_go())


def test_client_disconnect_mid_message(free_port):
    """Client đóng kết nối giữa message, server phải không sập."""
    async def _go():
        srv = EchoServer("127.0.0.1", free_port)
        server = await asyncio.start_server(srv.handle, "127.0.0.1", free_port)
        try:
            _, w = await asyncio.open_connection("127.0.0.1", free_port)
            w.write(b"\x00\x00\x00\x64")  # header báo 100 bytes, gửi 0 bytes
            await w.drain()
            w.close()
            await w.wait_closed()
            await asyncio.sleep(0.1)

            reader, writer = await asyncio.open_connection("127.0.0.1", free_port)
            try:
                rid = b"E" * REQUEST_ID_SIZE
                payload = b"still-alive"
                writer.write(encode_message(rid, payload))
                await writer.drain()
                r, p = await read_message(reader)
                assert r == rid
                assert p == payload
            finally:
                writer.close()
                await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()

    _run(_go())