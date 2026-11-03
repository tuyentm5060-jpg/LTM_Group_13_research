"""Wire format: 4-byte big-endian length followed by UTF-8 JSON."""

import asyncio
import json
import struct

MAX_FRAME_BYTES = 512 * 1024


class ProtocolError(ValueError):
    """Invalid frame or message."""


def validate_message(message: object, max_payload_bytes: int) -> dict:
    if not isinstance(message, dict):
        raise ProtocolError("Message must be an object")
    request_id = message.get("requestId")
    if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
        raise ProtocolError("requestId must be a nonempty string of at most 128 characters")
    payload = message.get("payload")
    if not isinstance(payload, str):
        raise ProtocolError("payload must be a string")
    if len(payload.encode("utf-8")) > max_payload_bytes:
        raise ProtocolError("Payload too large")
    return {"requestId": request_id, "payload": payload}


def encode_message(message: dict) -> bytes:
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if not 0 < len(body) <= MAX_FRAME_BYTES:
        raise ProtocolError("Frame too large")
    return struct.pack("!I", len(body)) + body


async def read_message(reader: asyncio.StreamReader, max_payload_bytes: int) -> dict:
    header = await reader.readexactly(4)
    size = struct.unpack("!I", header)[0]
    if not 0 < size <= MAX_FRAME_BYTES:
        raise ProtocolError("Invalid frame length")
    body = await reader.readexactly(size)
    try:
        message = json.loads(body.decode("utf-8"))
        return validate_message(message, max_payload_bytes)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError("Invalid message") from exc
