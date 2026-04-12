# Veltix

A modern, lightweight TCP networking library for Python — simple enough for beginners, solid enough for production.

[![PyPI](https://img.shields.io/pypi/v/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![Python](https://img.shields.io/pypi/pyversions/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![License](https://img.shields.io/github/license/NytroxDev/Veltix?cacheSeconds=300)](https://github.com/NytroxDev/Veltix/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/personalized-badge/veltix?period=total&units=NONE&left_color=BLACK&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/veltix)
[![Security Policy](https://img.shields.io/badge/security-policy-blue)](SECURITY.md)

Veltix provides a clean abstraction layer over TCP sockets, handling the low-level complexity so you can focus on your
application logic. It ships with message integrity verification, a structured binary protocol, request/response
correlation, automatic connection handshake, decorator-based message routing, auto-reconnect, and production-ready
logging — all with zero external dependencies.

**Performance highlights:** 110k+ msg/s throughput • 0.007ms average latency • 84KB idle memory • 64.4KB per client •
100% success rate

---

## Table of Contents

- [Why Veltix](#why-veltix)
- [Features](#features)
- [Performance](#performance)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Integrated Logger](#integrated-logger)
- [Request/Response Pattern](#requestresponse-pattern)
- [Built-in Ping/Pong](#built-in-pingpong)
- [Advanced Features](#advanced-features)
- [Comparison](#comparison)
- [Roadmap](#roadmap)
- [Migration Guide](#migration-guide)
- [Examples](#examples)
- [Security](#security)
- [Contributing](#contributing)
- [License](#license)

---

## Why Veltix

Working directly with Python's `socket` module or `asyncio` forces you to manage framing, concurrency, error handling,
and protocol design from scratch. Heavier frameworks like Twisted introduce steep learning curves and large dependency
trees.

Veltix sits in between: a focused library that handles the hard parts — connection management, message integrity,
threading, handshake, routing, and request correlation — while keeping the API surface small and the codebase readable.

**Designed for:**

- Developers who want structured TCP communication without dealing with `asyncio` internals
- Teams that need a maintainable, dependency-free networking layer in production
- Real-time applications and simulations
- Rapid prototyping of client/server applications
- Custom protocol experimentation

---

## Features

- **Simple API** — Get a working client/server in under 30 lines
- **High Performance** — 110k+ messages/second, 0.007ms latency
- **Message integrity** — Built-in CRC32 payload verification
- **Custom binary protocol** — Lightweight framing with TCP stream handling
- **Zero dependencies** — Pure Python standard library only
- **Multi-threaded** — Concurrent client handling out of the box
- **Automatic handshake** — HELLO/HELLO_ACK with version compatibility check on every connection
- **Thread-safe callbacks** — All callbacks run in a thread pool, slow handlers never block reception
- **Message routing** — `@server.route(MY_TYPE)` / `@client.route(MY_TYPE)` decorators for per-type handlers
- **Auto-reconnect** — Configurable retry with `DisconnectState` callbacks
- **Request/Response pattern** — `send_and_wait()` with configurable timeout
- **Built-in ping/pong** — Bidirectional latency measurement
- **Integrated logger** — Colorized, file-rotating, thread-safe logging
- **Performance modes** — `LOW` / `BALANCED` / `HIGH` presets for CPU/reactivity trade-off
- **Socket abstraction** — Swappable socket backends via `SocketCore` (Threading now, Selectors and Rust coming)
- **Client tags** — Attach arbitrary metadata to connected clients
- **Extensible** — Custom message types and event callbacks
- **Defensive design** — Strict validation and controlled failure handling

---

## Performance

> Benchmarked on Python 3.14.3 — 12-core CPU, 30.5 GB RAM, Linux. All tests run locally (loopback).

```
┌─────────────────────────────────────────────────────────────────────┐
│                    VELTIX PERFORMANCE RESULTS                       │
├─────────────────────┬───────────────────────────────────────────────┤
│  MEMORY             │                                               │
│  Idle server        │      84 KB                                    │
│  Per client         │      64.4 KB                                  │
│  50 clients total   │    24.95 MB                                   │
├─────────────────────┼───────────────────────────────────────────────┤
│  LATENCY (local)    │                                               │
│  Average            │   0.007 ms                                    │
│  P95                │   0.000 ms                                    │
│  P99                │   0.000 ms                                    │
│  Max                │   1.000 ms                                    │
├─────────────────────┼───────────────────────────────────────────────┤
│  FPS SIMULATION     │                                               │
│  64 players @64Hz   │   4,488 msg/s  –  100% success               │
│  128 players @20Hz  │   2,813 msg/s  –  100% success               │
├─────────────────────┼───────────────────────────────────────────────┤
│  BURST THROUGHPUT   │                                               │
│  Send               │ 110,011 msg/s                                 │
│  Receive            │  70,939 msg/s                                 │
│  Data               │    4.33 MB/s                                  │
├─────────────────────┼───────────────────────────────────────────────┤
│  CONCURRENT STRESS  │                                               │
│  100 clients        │  39,123 msg/s  –  100% success               │
└─────────────────────┴───────────────────────────────────────────────┘
```

**Ping/Pong** — 2,000 iterations, 100% success rate, 34,903 ping/s throughput.

**FPS simulation** — Veltix sustains a full 64-player game server at 64 tick/s and a 128-player server at 20 tick/s with
zero message loss.

**Burst throughput** — 10,000 × 64-byte messages processed in 0.091s.

**Concurrent stress** — 100 simultaneous clients each firing 100 messages; all 10,000 delivered with 100% success in
0.255s.

To run the benchmark suite yourself:

```bash
python benchmark.py

# Save results to JSON for sharing
python benchmark.py --save results.json
```

---

## Installation

```bash
pip install veltix
```

**Requirements:** Python 3.8+, no additional dependencies.

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
client.connect()  # Blocks until handshake is complete — safe to send immediately

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

Veltix includes a production-ready logging system with colorized output, automatic file rotation, and thread safety. It
follows a singleton pattern so the same instance is shared across your application.

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

`send_and_wait()` enables synchronous request/response communication over TCP. The client blocks until the server
replies with a matching `request_id`, or the timeout elapses.

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

### Message Routing

Use `@server.route()` and `@client.route()` to handle specific message types directly, without a global `on_recv`.
Routes take priority over `on_recv` and run in the thread pool.

```python
from veltix import Server, ServerConfig, MessageType, Response
from veltix.server.client_info import ClientInfo

CHAT = MessageType(code=200, name="chat")
STATUS = MessageType(code=201, name="status")

server = Server(ServerConfig(host="0.0.0.0", port=8080))


@server.route(CHAT)
def on_chat(response: Response, client: ClientInfo):
    print(f"[{client.addr[0]}] {response.content.decode()}")


@server.route(STATUS)
def on_status(response: Response, client: ClientInfo):
    print(f"Status from {client.addr[0]}: {response.content.decode()}")


server.start()
```

```python
from veltix import Client, ClientConfig, MessageType, Response

CHAT = MessageType(code=200, name="chat")

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))


@client.route(CHAT)
def on_chat(response: Response, client=None):
    print(f"Server: {response.content.decode()}")


client.connect()
```

Routes can also be registered programmatically:

```python
server.request_handler.register_route(CHAT, on_chat)
server.request_handler.unregister_route(CHAT)
```

### Client Tags

Attach arbitrary metadata to connected clients for tracking, filtering, or access control.

```python
from veltix import Server, ServerConfig, ClientInfo, Events

server = Server(ServerConfig(host="0.0.0.0", port=8080))


def on_connect(client: ClientInfo):
    client.add_tag("guest")


def on_message(client: ClientInfo, response):
    if client.has_tag("guest"):
        # Authenticate and upgrade
        client.remove_tag("guest")
        client.add_tag("authenticated", value="admin")

    if client.has_all_tags(["authenticated", "admin"]):
        print(f"Admin message from {client.addr[0]}")


server.set_callback(Events.ON_CONNECT, on_connect)
server.set_callback(Events.ON_RECV, on_message)
server.start()
```

Available tag methods on `ClientInfo`:

```python
client.add_tag("authenticated")  # Add a tag (returns False if already exists)
client.add_tag("role", value="admin")  # Add a tag with a value
client.has_tag("authenticated")  # Check for a single tag
client.has_all_tags(["auth", "admin"])  # Check all tags are present (AND)
client.has_any_tags(["admin", "mod"])  # Check at least one tag is present (OR)
client.get_tag("role")  # Retrieve a tag value
client.remove_tag("guest")  # Remove a tag
client.clear_tags()  # Remove all tags
```

### Socket Backend

Veltix abstracts the socket layer behind a `SocketCore` enum. The default is `THREADING` — future versions will add
`ASYNC` (selectors-based, v1.7.0) and `RUST` (Tokio via PyO3, v3.0.0).

```python
from veltix import ServerConfig, ClientConfig, SocketCore

# Default — one thread per client
server = Server(ServerConfig(host="0.0.0.0", port=8080, socket_core=SocketCore.THREADING))

# Coming in v1.7.0 — selectors-based, same API
# server = Server(ServerConfig(host="0.0.0.0", port=8080, socket_core=SocketCore.ASYNC))
```

Switching backends requires no changes to application code.

### Auto-Reconnect

Enable automatic reconnection by setting `retry` in `ClientConfig`. The `on_disconnect` callback receives a
`DisconnectState` with full context at every attempt.

```python
from veltix import Client, ClientConfig, Events
from veltix.client.client import DisconnectState

client = Client(ClientConfig(
    server_addr="127.0.0.1",
    port=8080,
    retry=5,  # number of reconnection attempts
    retry_delay=1.0,  # seconds between attempts
))


def on_disconnect(state: DisconnectState):
    if state.permanent:
        print(f"Permanently disconnected — reason: {state.reason.name}")
    else:
        print(f"Retrying... attempt {state.attempt}/{state.retry_max}")


client.set_callback(Events.ON_DISCONNECT, on_disconnect)
client.connect()

# Cancel retries at any time
client.stop_retry()

# Force a new attempt, optionally overriding retry_max
client.retry(max_=10)
```

### Performance Mode

```python
from veltix import ServerConfig, ClientConfig, PerformanceMode

# LOW    — socket timeout 1.0s, minimal CPU
# BALANCED — socket timeout 0.5s, default
# HIGH   — socket timeout 0.1s, fast disconnection detection

server = Server(ServerConfig(host="0.0.0.0", port=8080, performance_mode=PerformanceMode.HIGH))
client = Client(ClientConfig(server_addr="127.0.0.1", port=8080, performance_mode=PerformanceMode.HIGH))
```

### Buffer Size

```python
from veltix import ServerConfig, ClientConfig, BufferSize

# SMALL  — 1KB  (default)
# MEDIUM — 8KB
# LARGE  — 64KB
# HUGE   — 1MB

server = Server(ServerConfig(host="0.0.0.0", port=8080, buffer_size=BufferSize.LARGE))
```

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

### Client Callbacks

```python
from veltix import Client, ClientConfig, Events
from veltix.client.client import DisconnectState

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))

client.set_callback(Events.ON_CONNECT, lambda: print("Connected and handshake complete!"))
client.set_callback(Events.ON_RECV, lambda response: print(response.content.decode()))
client.set_callback(Events.ON_DISCONNECT, lambda state: print(f"Disconnected — permanent={state.permanent}"))

client.connect()
```

### Configuring the Thread Pool

```python
from veltix import ServerConfig, ClientConfig

# Increase workers for high-concurrency workloads with slow callbacks
server_config = ServerConfig(host="0.0.0.0", port=8080, max_workers=8)
client_config = ClientConfig(server_addr="127.0.0.1", port=8080, max_workers=8)
```

### Broadcasting

```python
# Broadcast to all connected clients
message = Request(CHAT, b"Server announcement")
sender.broadcast(message, server.get_all_clients_sockets())

# Broadcast with exclusion
sender.broadcast(message, server.get_all_clients_sockets(), except_clients=[client.conn])
```

### Utilities

```python
from veltix import format_bytes, encode_json, decode_json, encode_utf8, decode_utf8

# Human-readable byte formatting
format_bytes(148_000)  # "144.5 KB"
format_bytes(3_000_000)  # "2.86 MB"

# JSON helpers
data = encode_json({"key": "value"})  # bytes
obj = decode_json(data)  # dict

# UTF-8 helpers
raw = encode_utf8("hello")  # bytes
text = decode_utf8(raw)  # str
```

---

## Comparison

| Feature                | Veltix | `socket` | `asyncio` | Twisted |
|------------------------|:------:|:--------:|:---------:|:-------:|
| Simple API             |   ✓    |    ✗     |     ~     |    ✗    |
| High Performance       |   ✓    |    ~     |     ✓     |    ~    |
| Zero dependencies      |   ✓    |    ✓     |     ✓     |    ✗    |
| Custom protocol        |   ✓    |    ✗     |     ✗     |    ~    |
| Message integrity      |   ✓    |    ✗     |     ✗     |    ✗    |
| Multi-threading        |   ✓    |    ✗     |     ✗     |    ✓    |
| Request/Response       |   ✓    |    ✗     |     ~     |    ✓    |
| Built-in ping/pong     |   ✓    |    ✗     |     ✗     |    ✗    |
| Automatic handshake    |   ✓    |    ✗     |     ✗     |    ✗    |
| Message routing        |   ✓    |    ✗     |     ✗     |    ~    |
| Auto-reconnect         |   ✓    |    ✗     |     ~     |    ✓    |
| Non-blocking callbacks |   ✓    |    ✗     |     ✓     |    ✓    |
| Integrated logger      |   ✓    |    ✗     |     ~     |    ✓    |
| Client tags            |   ✓    |    ✗     |     ✗     |    ✗    |
| Swappable socket core  |   ✓    |    ✗     |     ✗     |    ✗    |

---

## Roadmap

### v1.6.2 — Protocol Optimization & Stability *(April 2026)*

- Optimized wire protocol (22-byte header, 4-byte request IDs, CRC32 integrity)
- Client module split (`config.py`, `disconnect.py`, `reconnect_handler.py`)
- Fixed reconnect flow on connection failures (no false "connected" state)
- Fixed `on_disconnect` callback reliability and disconnect state handling
- Fixed reconnection retry edge cases (`retry()` and internal reconnect loop)
- Improved server restart stability in reconnect scenarios
- Official minimum runtime lowered to **Python 3.8+**
- Benchmark module relocated to `veltix/benchmark.py`

### v1.4.0 — Handshake & Callbacks ✓ *(Released March 2026)*

- HELLO/HELLO_ACK handshake with version compatibility check
- Thread pool for non-blocking callback execution (`CallbackExecutor`)
- Blocking `connect()` — safe to send immediately after connecting
- `on_connect` / `on_disconnect` callbacks on Client

### v1.5.0 — Routing & Reconnect ✓ *(Released March 2026)*

- Decorator-based message routing (`@server.route(MY_TYPE)`, `@client.route(MY_TYPE)`)
- Auto-reconnect with configurable retry and `DisconnectState` callbacks
- `PerformanceMode` presets for CPU/reactivity trade-off
- `BufferSize` presets for common buffer configurations

### v1.6.0 — Socket Abstraction & Tags ✓ *(Released March 2026)*

- `BaseSocket` Protocol — universal socket interface
- `ThreadingSocket` — current implementation behind clean abstraction
- `SocketCore` enum — swappable socket backends with zero API changes
- `ClientInfo` tags — arbitrary metadata on connected clients
- `veltix.utils` — encoding helpers and `format_bytes`
- `max_connection = -1` — unlimited connections by default
- Benchmark suite with JSON export for community sharing

### v1.7.0 — Selectors *(June 2026)*

- `AsyncSocket` — selectors-based I/O, replaces one-thread-per-client
- Same API, 4–8× throughput improvement expected
- Switch via `SocketCore.ASYNC`

### v1.8.0 — Plugin System *(August 2026)*

- `VeltixBasePlugin` — extensible plugin architecture
- Permission system for plugin event access
- `server.register_plugin()` / `client.register_plugin()`
- `server.attach(TYPE, plugin, mode)` — route message types to plugins

### v2.0.0 — Encryption *(September 2026)*

- End-to-end encryption: ChaCha20 + X25519 + Ed25519
- Automatic key exchange and perfect forward secrecy

### v3.0.0 — Rust Core *(2027)*

- PyO3 bindings
- 10–100× throughput improvement
- `SocketCore.RUST`

---

## Migration Guide

### v1.6.0 → v1.6.2

Breaking changes in protocol/API:

- `request_id` is now `bytes` (4 bytes), not UUID string
- Wire format changed (header/hash/request_id), upgrade both client/server together
- Handshake version check now requires exact `major.minor.patch` match

- Minimum supported Python version is now **3.8+**
- Reconnect/disconnect behavior is more robust (faster fail on refused connections, reliable disconnect callbacks)
- `retry()` and reconnect loop edge cases were fixed for better stability under flaky networks

### v1.5.0 → v1.6.0

No breaking changes to public API.

- `ClientInfo` now has tag methods: `add_tag()`, `has_tag()`, `has_all_tags()`, `has_any_tags()`, `get_tag()`,
  `remove_tag()`, `clear_tags()`
- `ServerConfig.max_connection` default changed from `2` to `-1` (unlimited)
- New `ServerConfig` / `ClientConfig` field: `socket_core` (default: `SocketCore.THREADING`)
- `veltix.utils` now exports encoding helpers and `format_bytes`
- Benchmark suite now supports `--save results.json`

### v1.4.0 → v1.5.0

**Breaking change:** `on_disconnect` on the client now receives a `DisconnectState` argument.

```python
# Before (v1.4.0)
client.set_callback(Events.ON_DISCONNECT, lambda: print("Disconnected"))

# After (v1.5.0)
client.set_callback(Events.ON_DISCONNECT, lambda state: print(f"Disconnected — permanent={state.permanent}"))
```

New optional fields in `ClientConfig`: `retry`, `retry_delay`, `performance_mode`, `buffer_size`.

New optional fields in `ServerConfig`: `performance_mode`, `buffer_size`.

### v1.3.0 → v1.4.0

No breaking changes to public API.

- `on_connect` (server-side) now fires after the handshake is complete — `client.handshake_done` is always `True` when
  it fires.
- `connect()` (client-side) now blocks until the handshake is done. It is safe to send messages immediately after it
  returns.
- New `ClientConfig` fields: `handshake_timeout` (default: `5.0`), `max_workers` (default: `4`)
- New `ServerConfig` fields: `handshake_timeout` (default: `5.0`), `max_workers` (default: `4`)

### v1.2.x → v1.3.0

No breaking changes to public API.

### v1.1.x → v1.2.0

```python
# Before
from veltix import Bindings

server.bind(Bindings.ON_RECV, callback)

# After
from veltix import Events

server.set_callback(Events.ON_RECV, callback)
```

---

## Examples

Full examples are available in the [`examples/`](examples/) directory:

- **Echo Server** — `send_and_wait()` with request correlation
- **Chat Server** — Broadcast messaging in under 80 lines
- **Ping Example** — Bidirectional latency measurement

---

## Security

Message integrity is enforced via CRC32 payload verification on every message. If you discover a vulnerability, please
report it responsibly through our [Security Policy](SECURITY.md).

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
- **Documentation:** https://nytroxdev.github.io/Veltix/
- **Discord:** [discord.gg/NrEjSHtfMp](https://discord.gg/NrEjSHtfMp)
