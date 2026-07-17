# Veltix

> Python TCP, without the boilerplate.

[![Lines of code](https://img.shields.io/endpoint?url=https://ghloc.vercel.app/api/NytroxDev/Veltix/badge)](https://ghloc.vercel.app/NytroxDev/Veltix)
[![PyPI](https://img.shields.io/pypi/v/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![Python](https://img.shields.io/pypi/pyversions/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![License](https://img.shields.io/github/license/NytroxDev/Veltix?cacheSeconds=300)](https://github.com/NytroxDev/Veltix/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/personalized-badge/veltix?period=total&units=NONE&left_color=BLACK&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/veltix)
[![Security Policy](https://img.shields.io/badge/security-policy-blue)](SECURITY.md)
[![AI Guide](https://img.shields.io/badge/for_AI-AGENTS.md-purple)](AGENTS.md)

Sync, thread-friendly, zero dependencies : TCP done right.
Veltix handles framing, threading, handshake, routing, and reconnection
so you can focus on your application logic.

**Mature & tested** - 571+ tests · CI on Python 3.8-3.14 · 12+ releases

---

## Table of Contents

- [Why Veltix?](#why-veltix)
- [Raw Socket vs Veltix](#raw-socket-vs-veltix)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Key Features](#key-features)
- [Backend Comparison: Threading vs Async](#backend-comparison-threading-vs-async)
- [Performance](#performance)
- [API Overview](#api-overview)
- [When NOT to use Veltix](#when-not-to-use-veltix)
- [Comparison](#comparison)
- [Built with Veltix](#built-with-veltix)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## Why Veltix?

I wrote Veltix because I got tired of rewriting the same networking boilerplate every time I needed two programs to talk
to each other.

Raw sockets are powerful, but they leave framing, request routing, handshakes, reconnection, and thread management
entirely up to you. asyncio solves part of the problem, but adopting it often means committing your whole application to
an async architecture. Twisted is incredibly capable, but it comes with its own programming model and can feel more like
learning a framework than writing plain Python.

I wanted something different: a lightweight library that handles the repetitive networking work without forcing a
particular architecture. Define your message types, register your handlers, and focus on your application instead of
socket plumbing.

That's the idea behind Veltix: modern TCP communication with a simple, synchronous API, sensible defaults, and zero
dependencies.

---

## Raw Socket vs Veltix

**Echo server with raw sockets (15 lines):**

```python
import socket
import threading


def handle_client(conn, addr):
    while True:
        data = conn.recv(1024)
        if not data:
            break
        conn.sendall(data)
    conn.close()


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("0.0.0.0", 8080))
server.listen(5)

while True:
    conn, addr = server.accept()
    threading.Thread(target=handle_client, args=(conn, addr)).start()
```

**Same thing with Veltix (7 lines):**

```python
from veltix import Server, ServerConfig, ClientInfo, Response, MessageType, Request

ECHO = MessageType("echo")
server = Server(ServerConfig(host="0.0.0.0", port=8080))


@server.route(ECHO)
def on_echo(client: ClientInfo, response: Response) -> None:
    server.send(Request(ECHO, response.content), client)


server.start()
```

No manual framing. No thread management. No boilerplate.

**What you get out of the box:**

- **Message framing**: no more `recv()` loops and buffer handling
- **Protocol routing**: `@server.route(MY_TYPE)` instead of `if/elif` chains
- **Automatic handshake**: JSON raw-socket protocol with version compatibility
- **Built-in ping/pong**: bidirectional latency measurement, zero config
- **Auto-reconnect**: configurable retry with disconnect state callbacks
- **Message integrity**: CRC32 verification on every message
- **Request/Response**: `send_and_wait()` with timeout and correlation
- **Convenience send**: `server.send()` / `client.send()` — no need to touch `Sender` directly
- **Content decoding**: `response.text` and `response.json` — lazy, cached, zero-copy
- **Text & JSON payloads**: `Request(MY_TYPE, text="hello")` / `Request(MY_TYPE, json={"x": 1})`
- **Thread-safe callbacks**: slow handlers never block reception
- **Client tagging**: attach metadata, broadcast to groups
- **Integrated logger**: colorized, rotating, thread-safe
- **Structured event bus**: powered by [Avyra](https://github.com/NytroxDev/Avyra) — subscribe to lifecycle, message,
  protocol, and error events

**Designed for:** LAN tools, multiplayer games, real-time dashboards, custom protocols, IPC, remote tooling, file
transfer.

---

## Installation

```bash
pip install veltix
```

Requirements: Python 3.8+, no additional dependencies.

---

## Quick Start

**Server:**

```python
from veltix import Server, ServerConfig, ClientInfo, Response, MessageType, Request

CHAT = MessageType("chat")

server = Server(ServerConfig(host="0.0.0.0", port=8080))


@server.route(CHAT)
def on_message(client: ClientInfo, response: Response) -> None:
    print(f"[{client.ip}] {response.text}")
    server.broadcast(Request(CHAT, response.text))


server.start()

input("Press Enter to stop...")
server.close_all()
```

**Client:**

```python
from veltix import Client, ClientConfig, Response, MessageType, Request

CHAT = MessageType("chat")

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))


@client.route(CHAT)
def on_message(response: Response) -> None:
    print(f"Server: {response.text}")


client.connect()

client.send(Request(CHAT, text="Hello Server!"))
input("Press Enter to disconnect...")
client.disconnect()
```

```bash
python server.py
python client.py  # In a separate terminal
```

---

## Key Features

### Content Decoding

`Response` provides lazy, cached decoding helpers — no more `.content.decode()` everywhere:

```python
@server.route(MY_TYPE)
def handler(client: ClientInfo, response: Response) -> None:
    text = response.text          # str, cached after first call
    data = response.json          # Any (parsed JSON), cached
    is_json = response.is_json    # bool — safe check without raising
    is_text = response.is_text    # bool — safe check without raising
```

### Text & JSON Payloads

Build requests without manual encoding:

```python
Request(MY_TYPE, text="hello")           # encodes to UTF-8 automatically
Request(MY_TYPE, json={"key": "value"})  # serializes to JSON automatically
Request(MY_TYPE, content=b"\x00\x01")    # raw bytes when you need them
```

Exactly one payload argument is required. Passing zero or more than one raises `RequestError`.

### Request / Response Correlation

`send_and_wait()` sends a request and blocks until the matching response arrives:

```python
# Client side
response = client.send_and_wait(Request(MY_TYPE, b"data"), timeout=3.0)
if response:
    print(response.text)
```

```python
# Server side
response = server.send_and_wait(Request(MY_TYPE, b"data"), client, timeout=3.0)
```

### Server Convenience Methods

```python
server.send(request, client)                          # send to one client
server.broadcast(request)                             # send to everyone
server.broadcast(request, except_clients=[client])    # send to everyone except one
server.wait_until_closed()                            # block until close_all()
server.restart()                                      # stop + start
```

### Client Convenience Methods

```python
client.send(request)             # send to server
client.send_and_wait(request)    # send and wait for response
client.ping_server()             # measure latency (ms)
client.wait_until_closed()       # block until disconnect
client.stop_retry()              # cancel pending reconnection
```

### Client Tags

Attach metadata to clients, broadcast to filtered groups:

```python
@server.route(JOIN)
def on_join(client: ClientInfo, response: Response) -> None:
    client.add_tag("channel", response.text)

# Later — broadcast only to clients in the same channel
targets = server.get_clients_by_tag("channel", "general")
server.broadcast(Request(MSG, data), except_clients=None)  # manual filter via targets
```

---

## Backend Comparison: Threading vs Async

Veltix lets you switch between two socket backends via `SocketCore`. Pick the one that fits your use case.

| Criteria              | Threading (`SocketCore.THREADING`)           | Async (`SocketCore.ASYNC`)                     |
|-----------------------|----------------------------------------------|------------------------------------------------|
| **Model**             | One thread per client                        | Single-threaded event loop (selectors)         |
| **Best for**          | Simple apps, < 50 clients, predictable loads | High concurrency, 100+ clients, variable loads |
| **Concurrent stress** | ~32k msg/s                                   | **~83k msg/s (2.6x)**                          |
| **Idle memory**       | 21 KB server + 35 KB per client              | **4 KB server + 12 KB per client**             |
| **Latency**           | **0.032 ms**                                 | 0.036 ms                                       |
| **Debugging**         | Straightforward (stack traces = threads)     | Harder (event loop internals)                  |

**Quick rule of thumb:**

- Few clients, simple logic, want easy debugging? Use `THREADING`.
- Many clients, high throughput, memory-conscious? Use `ASYNC`.

```python
from veltix import Server, ServerConfig, SocketCore

server = Server(ServerConfig(socket_core=SocketCore.THREADING))  # or .ASYNC
```

---

## Performance

> Benchmarked on Python 3.14.5 : 12-core CPU, 30.5 GB RAM, Linux (loopback).

| Metric                             | Threading       | Async            |
|------------------------------------|-----------------|------------------|
| Concurrent stress (100 clients)    | 32,297 msg/s    | **82,937 msg/s** |
| Burst throughput                   | 49,287 / 39,517 | 49,878 / 39,909  |
| Average latency                    | 0.032 ms        | 0.036 ms         |
| Idle server memory                 | 21 KB           | 4 KB             |
| Per client memory (avg)            | 35 KB           | 12 KB            |
| FPS simulation (64 players @ 64Hz) | 4,490 msg/s     | 4,491 msg/s      |

Full benchmark details, methodology, and how to run them yourself : [PERFORMANCE.md](PERFORMANCE.md)

---

## API Overview

### Creating a Server

```python
from veltix import Server, ServerConfig, SocketCore, ClientInfo, Response

server = Server(ServerConfig(
    host="0.0.0.0",
    port=8080,
    buffer_size=1024,          # BufferSize.SMALL default
    max_connection=-1,         # -1 = unlimited
    max_workers=4,
    socket_core=SocketCore.ASYNC,
    id_window=30000,           # unique IDs per direction
))

server.start()
server.wait_until_closed()
server.close_all()
```

### Creating a Client

```python
from veltix import Client, ClientConfig, Response

client = Client(ClientConfig(
    server_addr="127.0.0.1",
    port=8080,
    retry=3,           # 0 = no reconnect
    retry_delay=1.0,
    socket_core=SocketCore.ASYNC,
))

client.connect()              # blocks until handshake done
client.disconnect()
client.wait_until_closed()
```

### Route Decorators

```python
@server.route(MY_TYPE)    # func(client: ClientInfo, response: Response) -> None
def on_server_msg(client, response): ...

@client.route(MY_TYPE)    # func(response: Response) -> None
def on_client_msg(response): ...
```

### Callbacks

```python
server.on_recv(callback)       # func(client: ClientInfo, response: Response)
server.on_connect(callback)    # func(client: ClientInfo)
server.on_disconnect(callback) # func(client: ClientInfo)

client.on_recv(callback)       # func(response: Response)
client.on_connect(callback)    # func()
client.on_disconnect(callback) # func(state: DisconnectState)
```

### Ping

```python
latency_ms = client.ping_server(timeout=3.0)          # Optional[float]
latency_ms = server.ping_client(client, timeout=3.0)  # Optional[float]
```

### Event Bus (v1.9.0+)

```python
from veltix.internal.events import ServerEvent, ClientEvent

server.bus.subscribe(ServerEvent.ON_CONNECT, callback)
server.bus.subscribe(ClientEvent.ON_DISCONNECT, callback)
```

### Logger

```python
from veltix import Logger, LoggerConfig, LogLevel

logger = Logger.get_instance(LoggerConfig(level=LogLevel.DEBUG))
logger.info("Hello")
logger.set_level(LogLevel.WARNING)
```

---

## When NOT to use Veltix

Veltix is great for TCP, but not every problem is a TCP problem.

- **HTTP/REST APIs**: use Flask, FastAPI, or Django REST Framework
- **Browser clients**: Veltix speaks raw TCP, not WebSocket; use `websockets` or Socket.IO
- **Async-first codebases**: Veltix is sync by design; use `asyncio` directly if your whole project is async
- **Ultra high throughput (>100k msg/s per connection)**: consider a compiled language for the hot path
- **Single request-response**: if you just need to fetch something once, `requests` or `urllib` is simpler

Everything else? Veltix has you covered.

---

## Comparison

| Feature                | Veltix | `socket` | `asyncio` | Twisted |
|------------------------|:------:|:--------:|:---------:|:-------:|
| High-level API         |   ✓    |    ✗     |     ~     |    ✗    |
| Zero dependencies      |   ✓    |    ✓     |     ✓     |    ✗    |
| No async required      |   ✓    |    ✓     |     ✗     |    ✗    |
| Message framing        |   ✓    |    ✗     |     ✗     |    ~    |
| Message integrity      |   ✓    |    ✗     |     ✗     |    ✗    |
| Automatic handshake    |   ✓    |    ✗     |     ✗     |    ✗    |
| Request/Response       |   ✓    |    ✗     |     ~     |    ✓    |
| Message routing        |   ✓    |    ✗     |     ✗     |    ~    |
| Auto-reconnect         |   ✓    |    ✗     |     ~     |    ✓    |
| Non-blocking callbacks |   ✓    |    ✗     |     ✓     |    ✓    |
| Built-in ping/pong     |   ✓    |    ✗     |     ✗     |    ✗    |
| Client tags            |   ✓    |    ✗     |     ✗     |    ✗    |
| Swappable backends     |   ✓    |    ✗     |     ✗     |    ✗    |
| Integrated logger      |   ✓    |    ✗     |     ~     |    ✓    |
| Content decoding       |   ✓    |    ✗     |     ✗     |    ✗    |

> ✓ Built-in &nbsp;&nbsp; ~ Possible but requires manual setup &nbsp;&nbsp; ✗ Not provided (you implement it yourself)

---

## Built with Veltix

Projects using Veltix in production:

- **[Nexo](https://github.com/NytroxDev/Nexo)** : Fast LAN file transfer tool CLI + GUI.
  Uses Veltix's TCP server, client tags, route decorators, and `send_and_wait()` for
  reliable chunked file transfers with concurrent connection handling.

> Built something with Veltix ? [Open a PR](https://github.com/NytroxDev/Veltix/pulls)
> or [start a discussion](https://github.com/NytroxDev/Veltix/discussions) to add your project.

---

## Documentation

- [Full documentation](docs/index.md)
- [Advanced features](docs/guides/advanced.md)
- [Migration guide](docs/guides/migration.md)
- [Changelog](CHANGELOG.md)
- [Examples](examples/)

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request.

- Bug reports : [Open an issue](https://github.com/NytroxDev/Veltix/issues)
- Discussions : [Join the Discord](https://discord.gg/gz8K369a6p)
- Pull requests : Follow the contribution guide

---

## License

MIT License : see [LICENSE](LICENSE) for details.

---

## Links

- GitHub : [NytroxDev/Veltix](https://github.com/NytroxDev/Veltix)
- PyPI : [pypi.org/project/veltix](https://pypi.org/project/veltix)
- Documentation : https://nytroxdev.github.io/Veltix/
- Discord : [discord.gg/gz8K369a6p](https://discord.gg/gz8K369a6p)
