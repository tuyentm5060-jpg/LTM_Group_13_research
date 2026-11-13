import asyncio
import uuid
from dataclasses import dataclass

from common.protocol import ProtocolError, encode_message, read_message

PAYLOAD_SIZE = 1024


@dataclass
class ClientResult:
    client_id: int
    request_id: str
    status: str
    detail: str


def build_request():
    """Create a unique requestId and a payload of exactly 1024 UTF-8 bytes."""
    payload = "A" * PAYLOAD_SIZE
    assert len(payload.encode("utf-8")) == PAYLOAD_SIZE
    return {"requestId": str(uuid.uuid4()), "payload": payload}


async def run_client(client_id, host, port, stop_event,
                     connect_timeout=5, response_timeout=3):
    request = build_request()
    request_id = request["requestId"]
    writer = None

    if stop_event.is_set():
        return ClientResult(client_id, request_id, "STOPPED", "Stopped before connect")

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=connect_timeout
        )

        if stop_event.is_set():
            return ClientResult(client_id, request_id, "STOPPED", "Stopped before send")

        try:
            writer.write(encode_message(request))
            async with asyncio.timeout(response_timeout):
                await writer.drain()
                response = await read_message(reader, PAYLOAD_SIZE)
        except asyncio.TimeoutError:
            return ClientResult(
                client_id, request_id, "FAILED",
                "Timeout sending request or waiting for complete response"
            )

        if response["requestId"] != request_id:
            return ClientResult(
                client_id, request_id, "FAILED",
                "Response requestId does not match"
            )
        if response["payload"] != request["payload"]:
            return ClientResult(
                client_id, request_id, "FAILED",
                "Response payload does not match"
            )

        return ClientResult(
            client_id, request_id, "SUCCESS", "Request sent and response verified"
        )

    except asyncio.TimeoutError:
        return ClientResult(client_id, request_id, "FAILED", "Connection timeout")
    except asyncio.IncompleteReadError:
        return ClientResult(
            client_id, request_id, "FAILED",
            "Server closed connection before a complete response was received"
        )
    except OSError as exc:
        return ClientResult(client_id, request_id, "FAILED", f"Connection error: {exc}")
    except ProtocolError as exc:
        return ClientResult(client_id, request_id, "FAILED", f"Invalid response: {exc}")
    except Exception as exc:
        return ClientResult(client_id, request_id, "FAILED", f"Unexpected error: {exc}")
    finally:
        if writer is not None:
            writer.close()
            try:
                async with asyncio.timeout(response_timeout):
                    await writer.wait_closed()
            except Exception:
                pass
