import asyncio
import json
import uuid
from dataclasses import dataclass

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

        # Standalone protocol: one UTF-8 JSON object per line (newline delimiter).
        # payload field = 1024 bytes; complete JSON frame is larger than 1024 bytes.
        frame = (json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8")
        writer.write(frame)
        await writer.drain()

        try:
            response_line = await asyncio.wait_for(
                reader.readline(), timeout=response_timeout
            )
        except asyncio.TimeoutError:
            return ClientResult(
                client_id, request_id, "SENT",
                "Request sent; no response received before timeout"
            )

        if not response_line:
            return ClientResult(
                client_id, request_id, "SENT",
                "Request sent; server closed connection without a response"
            )

        response = json.loads(response_line.decode("utf-8"))
        if response.get("requestId") != request_id:
            return ClientResult(
                client_id, request_id, "FAILED",
                "Response requestId does not match"
            )

        return ClientResult(
            client_id, request_id, "SUCCESS", "Request sent and response verified"
        )

    except (OSError, asyncio.TimeoutError) as exc:
        return ClientResult(client_id, request_id, "FAILED", str(exc))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return ClientResult(client_id, request_id, "FAILED", f"Invalid response: {exc}")
    except Exception as exc:
        return ClientResult(client_id, request_id, "FAILED", f"Unexpected error: {exc}")
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
