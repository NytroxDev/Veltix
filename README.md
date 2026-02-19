# Veltix

A modern, lightweight TCP networking library for Python — simple enough for beginners, solid enough for production.

[![PyPI](https://img.shields.io/pypi/v/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![Python](https://img.shields.io/pypi/pyversions/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![License](https://img.shields.io/github/license/NytroxDev/Veltix?cacheSeconds=300)](https://github.com/NytroxDev/Veltix/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/personalized-badge/veltix?period=total&units=NONE&left_color=BLACK&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/veltix)
[![Security Policy](https://img.shields.io/badge/security-policy-blue)](SECURITY.md)

Veltix provides a clean abstraction layer over TCP sockets, handling the low-level complexity so you can focus on your application logic. It ships with message integrity verification, a structured binary protocol, request/response correlation, and production-ready logging — all with zero external dependencies.

---

## Table of Contents

- [Why Veltix](#why-veltix)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Logger](#integrated-logger)
- [Request / Response](#requestresponse-pattern)
- [Ping / Pong](#built-in-pingpong)
- [Advanced Features](#advanced-features)
- [Comparison](#comparison)
- [Roadmap](#roadmap)
- [Security](#security)
- [Contributing](#contributing)
- [License](#license)

---

## Why Veltix

Working directly with Python's `socket` module or `asyncio` forces you to manage framing, concurrency, error handling, and protocol design from scratch. Heavier frameworks like Twisted introduce steep learning curves and large dependency trees.

Veltix sits in between: a focused library that handles the hard parts — connection management, message integrity, threading, and request correlation — while keeping the API surface small and the codebase readable.

**Designed for:**
- Developers who want structured TCP communication without dealing with `asyncio` internals
- Teams that need a maintainable, dependency-free networking layer in production
- Rapid prototyping of client/server applications
- Custom protocol experimentation

---

## Features

- **Simple API** — Get a working client/server in under 30 lines
- **Message integrity** — Built-in SHA-256 payload verification
- **Custom binary protocol** — Lightweight framing with structured message types
- **Zero dependencies** — Pure Python standard library only
- **Multi-threaded** — Concurrent client handling out of the box
- **Request/Response pattern** — `send_and_wait()` with configurable timeout
- **Built-in ping/pong** — Bidirectional latency measurement
- **Integrated logger** — Colorized, file-rotating, thread-safe logging
- **Extensible** — Custom message types and event callbacks
- **Defensive design** — Strict validation and controlled failure handling

---

## Installation

```bash
pip install veltix
```

**Requirements:** Python 3.10+, no additional dependencies.

---

## Quick Start

The following example implements a basic echo server and client.

**Server (`server.py`):**

```python
from veltix import Server, ClientInfo, ServerConfig, Response, MessageType, Request, Events

CHAT = MessageType(code=200, name="chat")

config = ServerConfig(host="0.0.0.0", port=8080)
server = Server(config)
sender = server.get_sender()


def on_message(client: ClientInfo, response: Response):
    print(f"[{client.addr[0]}] {response.content.decode()}")
    reply = Request(CHAT, f"Echo: {response.content.decode()}".encode())
    sender.broadcast(reply, server.get_all_clients_sockets())


server.set_callback(Events.ON_RECV, on_message)
server.start()

input("Press Enter to stop...")
server.close_all()
```

**Client (`client.py`):**

```python
from veltix import Client, Response, ClientConfig, MessageType, Request, Events

CHAT = MessageType(code=200, name="chat")

config = ClientConfig(server_addr="127.0.0.1", port=8080)
client = Client(config)
sender = client.get_sender()


def on_message(response: Response):
    print(f"Server: {response.content.decode()}")


client.set_callback(Events.ON_RECV, on_message)
client.connect()

msg = Request(CHAT, b"Hello Server!")
sender.send(msg)

input("Press Enter to disconnect...")
client.disconnect()
```

```bash
python server.py
python client.py  # In a separate terminal
```

---

## Integrated Logger

Veltix includes a production-ready logging system with colorized output, automatic file rotation, and thread safety. It follows a singleton pattern so the same instance is shared across your application.

### Basic Usage

```python
from veltix import Logger, LogLevel

logger = Logger.get_instance()

logger.trace("Detailed trace information")
logger.debug("Debug information")
logger.info("General information")
logger.success("Operation successful")
logger.warning("Warning message")
logger.error("Error occurred")
logger.critical("Critical failure")
```

### Configuration

```python
from veltix import Logger, LoggerConfig, LogLevel
from pathlib import Path

config = LoggerConfig(
    level=LogLevel.DEBUG,
    enabled=True,
    use_colors=True,
    show_timestamp=True,
    show_caller=True,
    show_level=True,
    file_path=Path("logs/veltix.log"),
    file_rotation_size=10 * 1024 * 1024,  # 10 MB
    file_backup_count=5,
    async_write=False,
    buffer_size=100,
)

logger = Logger.get_instance(config)
```

### Output Format

```
[14:23:45.123] INFO  [server.py:45] Server listening on 0.0.0.0:8080
[14:23:46.456] OK    [client.py:78] Successfully connected to server
[14:23:47.789] DEBUG [sender.py:92] Sent 156 bytes via client (request_id: a3f2...)
[14:23:48.012] WARN  [network.py:34] Connection issue: ConnectionResetError
[14:23:49.345] ERROR [request.py:89] Parse error: Hash mismatch — corrupted data
```

### Available Log Levels

| Level      | Severity |
|------------|----------|
| `TRACE`    | 5        |
| `DEBUG`    | 10       |
| `INFO`     | 20       |
| `SUCCESS`  | 25       |
| `WARNING`  | 30       |
| `ERROR`    | 40       |
| `CRITICAL` | 50       |

```python
# Change level at runtime
logger.set_level(LogLevel.WARNING)
```

---

## Request/Response Pattern

`send_and_wait()` enables synchronous request/response communication over TCP. The client blocks until the server replies with a matching `request_id`, or the timeout elapses.

**Client:**

```python
from veltix import Client, ClientConfig, MessageType, Request

ECHO = MessageType(code=201, name="echo")
client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))
client.connect()

request = Request(ECHO, b"Hello Server!")
response = client.send_and_wait(request, timeout=5.0)

if response:
    print(f"Response: {response.content.decode()}")
    print(f"Latency: {response.latency}ms")
else:
    print("Request timed out")

client.disconnect()
```

**Server:**

```python
from veltix import Server, ServerConfig, MessageType, Request, Events

ECHO = MessageType(code=201, name="echo")
server = Server(ServerConfig(host="0.0.0.0", port=8080))


def on_message(client, response):
    # Return the same request_id to correlate the response
    reply = Request(response.type, response.content, request_id=response.request_id)
    server.get_sender().send(reply, client=client.conn)


server.set_callback(Events.ON_RECV, on_message)
server.start()

input("Press Enter to stop...")
server.close_all()
```

---

## Built-in Ping/Pong

Veltix handles PING/PONG internally. No manual implementation required.

**Client pinging the server:**

```python
from veltix import Client, ClientConfig

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))
client.connect()

latency = client.ping_server(timeout=2.0)
print(f"Latency: {latency}ms" if latency else "Ping timed out")

client.disconnect()
```

**Server pinging a client:**

```python
from veltix import Server, ServerConfig, Events

server = Server(ServerConfig(host="0.0.0.0", port=8080))


def on_connect(client):
    latency = server.ping_client(client, timeout=2.0)
    if latency:
        print(f"Client {client.addr} latency: {latency}ms")


server.set_callback(Events.ON_CONNECT, on_connect)
server.start()

input("Press Enter to stop...")
server.close_all()
```

---

## Advanced Features

### Custom Message Types

Message type codes are divided into ranges by convention:

```python
from veltix import MessageType

# System messages (0–199)
PING = MessageType(0, "ping", "System ping")

# Application messages (200–499)
CHAT = MessageType(200, "chat", "Chat message")
FILE_TRANSFER = MessageType(201, "file", "File transfer")

# Plugin messages (500+)
CUSTOM = MessageType(500, "plugin", "Custom plugin message")
```

### Event Callbacks

```python
from veltix import Server, Events

server = Server(config)

server.set_callback(Events.ON_CONNECT, lambda client: print(f"Connected: {client.addr}"))
server.set_callback(Events.ON_RECV, lambda client, msg: print(f"Message from {client.addr}"))
server.set_callback(Events.ON_DISCONNECT, lambda client: print(f"Disconnected: {client.addr}"))
```

### Broadcasting

```python
# Broadcast to all connected clients
message = Request(CHAT, b"Server announcement")
sender.broadcast(message, server.get_all_clients_sockets())

# Broadcast with exclusion
sender.broadcast(message, server.get_all_clients_sockets(), except_clients=[client.conn])
```

---

## Comparison

| Feature             | Veltix | `socket` | `asyncio` | Twisted |
|---------------------|:------:|:--------:|:---------:|:-------:|
| Simple API          | ✓      | ✗        | ~         | ✗       |
| Zero dependencies   | ✓      | ✓        | ✓         | ✗       |
| Custom protocol     | ✓      | ✗        | ✗         | ~       |
| Message integrity   | ✓      | ✗        | ✗         | ✗       |
| Multi-threading     | ✓      | ✗        | ✗         | ✓       |
| Request/Response    | ✓      | ✗        | ~         | ✓       |
| Built-in ping/pong  | ✓      | ✗        | ✗         | ✗       |
| Integrated logger   | ✓      | ✗        | ~         | ✓       |

---

## Roadmap

### v1.2.0 — Logging & Stability ✓ *(Released February 2026)*

- Integrated logging system with colors and file rotation
- Enhanced error handling and data validation
- Improved broadcasting with exclusion support
- API update: `set_callback()` / `Events` replacing `bind()` / `Bindings`
- Foundation for v1.3.0 handshake system

### v1.3.0 — Handshake & Authentication *(March 2026 — In Development)*

- Connection handshake protocol (HELLO messages)
- Client authentication and server-side validation
- Protocol version negotiation

### v2.0.0 — Encrypted Transport *(Planned)*

- End-to-end encryption: ChaCha20 + X25519 + Ed25519
- Automatic key exchange and perfect forward secrecy

### v3.0.0 — Performance *(Fall 2026 — Research)*

- Rust core via PyO3
- Targeted 10–100× throughput improvement

### v4.0.0+ *(2027+)*

- UDP support
- WebSocket bridge
- Compression
- Plugin ecosystem

---

## Migration Guide

### v1.1.x → v1.2.0

```python
# Before
from veltix import Bindings
server.bind(Bindings.ON_RECV, callback)

# After
from veltix import Events
server.set_callback(Events.ON_RECV, callback)
```

### v1.2.0 → v1.2.1

No breaking changes. This release fixes race conditions in multi-threaded client handling and adds the `ON_DISCONNECT` event and `Request.respond()` helper.

---

## Examples

Full examples are available in the [`examples/`](examples/) directory:

- **Echo Server** — `send_and_wait()` with request correlation
- **Chat Server** — Broadcast messaging in under 80 lines
- **Ping Example** — Bidirectional latency measurement

---

## Security

Message integrity is enforced via SHA-256 payload verification on every message. If you discover a vulnerability, please report it responsibly through our [Security Policy](SECURITY.md).

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request.

- **Bug reports:** [Open an issue](https://github.com/NytroxDev/Veltix/issues)
- **Discussions:** [Join the Discord](https://discord.gg/NrEjSHtfMp)
- **Pull requests:** Follow the contribution guide

### Core Team

- **Nytrox** — Creator & Lead Developer

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Links

- **GitHub:** [NytroxDev/Veltix](https://github.com/NytroxDev/Veltix)
- **PyPI:** [pypi.org/project/veltix](https://pypi.org/project/veltix)
- **Documentation:** Coming soon
- **Discord:** [discord.gg/NrEjSHtfMp](https://discord.gg/NrEjSHtfMp)
