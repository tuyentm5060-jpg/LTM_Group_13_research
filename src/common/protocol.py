"""Length-prefix framing protocol dùng chung cho Server và Load Generator.

Frame:
    [4 bytes big-endian uint32: body length = len(requestId) + len(payload)]
    [16 bytes requestId]
    [payload: 0..MAX_PAYLOAD bytes]
"""

import asyncio
import struct

HEADER_SIZE = 4
REQUEST_ID_SIZE = 16
MAX_PAYLOAD = 64 * 1024  # 64 KB


class ProtocolError(Exception):
    """Raised khi message không hợp lệ (sai requestId size, payload vượt giới hạn...)."""


def encode_message(request_id: bytes, payload: bytes) -> bytes:
    if len(request_id) != REQUEST_ID_SIZE:
        raise ProtocolError(
            f"request_id phải đúng {REQUEST_ID_SIZE} bytes, nhận {len(request_id)}"
        )
    if len(payload) > MAX_PAYLOAD:
        raise ProtocolError(f"payload quá lớn: {len(payload)} > {MAX_PAYLOAD}")
    body = request_id + payload
    header = struct.pack(">I", len(body))
    return header + body


async def read_message(
    reader: asyncio.StreamReader, max_payload: int = MAX_PAYLOAD
) -> tuple[bytes, bytes]:
    """Đọc đủ một message, không giả định readexactly trả về một lần.

    Raise:
        asyncio.IncompleteReadError nếu peer đóng giữa chừng.
        ProtocolError nếu length không hợp lệ.
    """
    header = await reader.readexactly(HEADER_SIZE)
    (length,) = struct.unpack(">I", header)
    if length < REQUEST_ID_SIZE:
        raise ProtocolError(f"body quá ngắn: {length} < {REQUEST_ID_SIZE}")
    if length > REQUEST_ID_SIZE + max_payload:
        raise ProtocolError(
            f"body quá lớn: {length} > {REQUEST_ID_SIZE + max_payload}"
        )
    body = await reader.readexactly(length)
    return body[:REQUEST_ID_SIZE], body[REQUEST_ID_SIZE:]


def percentile(sorted_vals: list, p: float):
    """Percentile dùng nội suy tuyến tính (khớp numpy.percentile mặc định)."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)