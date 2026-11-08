import asyncio

import pytest

from src.common.protocol import (
    HEADER_SIZE,
    MAX_PAYLOAD,
    REQUEST_ID_SIZE,
    ProtocolError,
    encode_message,
    percentile,
    read_message,
)


def test_encode_decode_roundtrip():
    rid = b"A" * REQUEST_ID_SIZE
    payload = b"hello"
    msg = encode_message(rid, payload)
    assert len(msg) == HEADER_SIZE + REQUEST_ID_SIZE + len(payload)

    async def _go():
        reader = asyncio.StreamReader()
        reader.feed_data(msg)
        reader.feed_eof()
        return await read_message(reader)

    r, p = asyncio.run(_go())
    assert r == rid
    assert p == payload


def test_encode_bad_request_id():
    with pytest.raises(ProtocolError):
        encode_message(b"short", b"x")


def test_encode_payload_too_large():
    with pytest.raises(ProtocolError):
        encode_message(b"A" * REQUEST_ID_SIZE, b"x" * (MAX_PAYLOAD + 1))


def test_read_message_in_split_delivery():
    """Mô phỏng TCP trả về header và body ở các chunk khác nhau."""
    rid = b"B" * REQUEST_ID_SIZE
    payload = b"hello world, split!"
    msg = encode_message(rid, payload)

    async def _go():
        reader = asyncio.StreamReader()
        for i in range(0, len(msg), 3):
            reader.feed_data(msg[i:i + 3])
        reader.feed_eof()
        return await read_message(reader)

    r, p = asyncio.run(_go())
    assert r == rid
    assert p == payload


def test_read_message_rejects_oversize_length():
    import struct

    async def _go():
        reader = asyncio.StreamReader()
        # length vượt giới hạn
        reader.feed_data(struct.pack(">I", REQUEST_ID_SIZE + MAX_PAYLOAD + 1))
        return await read_message(reader)

    with pytest.raises(ProtocolError):
        asyncio.run(_go())


def test_percentile_basic():
    vals = list(range(1, 101))
    assert percentile(vals, 0.5) == 50.5
    assert percentile(vals, 0.95) == pytest.approx(95.05, rel=1e-3)
    assert percentile([], 0.95) is None
    assert percentile([5], 0.95) == 5