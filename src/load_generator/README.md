# TCP Load Generator — Trần Nguyễn Du

This module contains the independently developed Load Generator work.

## Folder layout

```text
src/
└── load_generator/
    ├── client/
    │   ├── __init__.py
    │   ├── tcp_client.py
    │   └── client_manager.py
    ├── gui/
    │   ├── __init__.py
    │   └── main_window.py
    ├── __init__.py
    ├── generator.py
    ├── main.py
    ├── README.md
    └── requirements.txt
```

## Scope

- Creates multiple concurrent TCP clients with `asyncio`.
- Provides a Tkinter GUI to configure server host, port, and client count.
- Each client creates a unique `requestId` (UUID) and sends a `payload` of exactly 1024 UTF-8 bytes.
- Displays each client's result and activity in the GUI.

## Requirements

- Python 3.10 or newer.
- Tkinter (normally included with the standard Windows Python installer).
- No third-party packages are required.

## Run from the repository root

```bash
python -m src.load_generator.main
```

## TCP message framing

This standalone implementation currently sends one UTF-8 JSON object followed by a newline (JSON Lines). The `payload` value is exactly 1024 bytes; the complete JSON message is larger because it includes the request ID and JSON framing.

The server must read one line, parse the JSON, and return a JSON line containing the same `requestId`, for example:

```json
{"requestId":"unique-uuid","status":"received"}
```

**Compatibility note:** this JSON Lines framing is not the same as a 4-byte big-endian length-prefixed protocol. If the group's server uses the latter, the client framing/response handling must be adapted before connecting to that server.

## Client result statuses

- `SUCCESS`: a response was received and its `requestId` matched.
- `SENT`: request was sent, but no response was received before timeout or close.
- `FAILED`: connection, send, or response validation failed.
- `STOPPED`: the client was stopped before connecting or sending.
