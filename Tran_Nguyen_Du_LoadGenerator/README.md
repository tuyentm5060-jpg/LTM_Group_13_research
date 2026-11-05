# Trần Nguyễn Du - Standalone Load Generator

This is a standalone implementation of only the assigned Load Generator work.
It is not merged into or dependent on the group's repository.

## Scope

1. asyncio-based concurrent TCP clients.
2. Basic Load Generator GUI (host, port, client count, Start/Stop, activity log).
3. TCP client sends one request containing:
   - `requestId`: unique UUID.
   - `payload`: exactly 1024 UTF-8 bytes.

## Requirements

- Python 3.10 or newer.
- Tkinter (normally included with the standard Windows Python installer).
- No third-party Python packages.

## Run

Open Command Prompt in this folder and execute:

```cmd
python main.py
```

Enter the Server IP, Port, and number of clients, then click Start.

## Standalone TCP message format

For this independent source package, messages use JSON Lines:
one UTF-8 JSON object followed by `\n`.

Example:

```json
{"requestId":"unique-uuid","payload":"AAAA..."}
```

The payload value is exactly 1024 bytes. The complete JSON frame is larger than
1024 bytes because it also contains the requestId, field names, JSON syntax,
and newline delimiter.

The server must read one line, parse the JSON, and respond with one JSON line
containing the same `requestId`, for example:

```json
{"requestId":"unique-uuid","status":"received"}
```

This is a standalone protocol convention. If connecting to another server,
its framing and response format must match this README or the TCP client must
be adapted accordingly.

## Folder structure

```text
Tran_Nguyen_Du_LoadGenerator/
├── client/
│   ├── __init__.py
│   ├── tcp_client.py
│   └── client_manager.py
├── gui/
│   ├── __init__.py
│   └── main_window.py
├── load_generator/
│   ├── __init__.py
│   └── generator.py
├── main.py
├── requirements.txt
└── README.md
```

## Status meanings

- `SUCCESS`: request sent and response requestId verified.
- `SENT`: request sent, but no valid response was received before timeout or close.
- `FAILED`: connection, sending, or response validation failed.
- `STOPPED`: client stopped before connecting or sending.
