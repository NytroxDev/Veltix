# Veltix

> Python TCP, without the boilerplate.

[![CI](https://github.com/NytroxDev/Veltix/actions/workflows/ci.yml/badge.svg)](https://github.com/NytroxDev/Veltix/actions/workflows/ci.yml)
[![Lines of code](https://img.shields.io/endpoint?url=https://ghloc.vercel.app/api/NytroxDev/Veltix/badge)](https://ghloc.vercel.app/NytroxDev/Veltix)
[![PyPI](https://img.shields.io/pypi/v/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![Python](https://img.shields.io/pypi/pyversions/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![License](https://img.shields.io/github/license/NytroxDev/Veltix?cacheSeconds=300)](https://github.com/NytroxDev/Veltix/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/personalized-badge/veltix?period=total&units=NONE&left_color=BLACK&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/veltix)
[![Security Policy](https://img.shields.io/badge/security-policy-blue)](SECURITY.md)
[![AI Guide](https://img.shields.io/badge/for_AI-AGENTS.md-purple)](AGENTS.md)

[v2.0.0 release notes](v2.0.0.md)

Sync, thread-friendly, zero dependencies : TCP done right. Veltix handles framing, threading, handshake, routing, and
reconnection so you can focus on your application logic.

**Mature & tested** - 638 tests · CI on Python 3.11-3.14 · Rust-powered hot path

---

## Table of Contents

- [Why Veltix?](#why-veltix)
- [Raw Socket vs Veltix](#raw-socket-vs-veltix)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Key Features](#key-features)
- [Rust-powered hot path](#rust-powered-hot-path)
- [Backend Comparison: Threading vs Async](#backend-comparison-threading-vs-async)
- [Performance](#performance)
- [When NOT to use Veltix](#when-not-to-use-veltix)
- [Comparison](#comparison)
- [In Development](#in-development)
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
- **Convenience send**: `server.send()` / `client.send()` : no need to touch `Sender` directly
- **Content decoding**: `response.text` and `response.json` : lazy, cached, zero-copy
- **Text & JSON payloads**: `Request(MY_TYPE, text="hello")` / `Request(MY_TYPE, json={"x": 1})`
- **Thread-safe callbacks**: slow handlers never block reception
- **Client tagging**: attach metadata, broadcast to groups
- **Integrated logger**: colorized, rotating, thread-safe
- **Structured event bus**: powered by [Avyra](https://github.com/NytroxDev/Avyra) : subscribe to lifecycle, message,
  protocol, and error events
- **Rust-powered engine**: framing / parse / compile in native Rust - with automatic pure-Python fallback

**Designed for:** LAN tools, multiplayer games, real-time dashboards, custom protocols, IPC, remote tooling, file
transfer.

---

## Installation

```bash
pip install veltix
```

Requirements: Python 3.11+, no runtime dependencies. Prebuilt wheels ship the compiled Rust engine (one `cp311-abi3`
wheel per platform); when the native component is unavailable, Veltix automatically falls back to the pure-Python
implementation. Building from source requires a Rust toolchain (handled automatically by the maturin build backend).

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

```python
# Content decoding (lazy, cached)
response.text  # UTF-8 string
response.json  # parsed JSON
response.is_json  # bool, no exception

# Text & JSON payloads (no manual encoding)
Request(MY_TYPE, text="hello")
Request(MY_TYPE, json={"key": "value"})

# Request/Response correlation
response = client.send_and_wait(Request(MY_TYPE, b"data"), timeout=3.0)

# Server convenience
server.send(request, client)
server.broadcast(request)
server.broadcast(request, except_clients=[client])
server.wait_until_closed()
server.restart()

# Client convenience
client.send(request)
client.send_and_wait(request, timeout=5.0)
client.ping_server()
client.wait_until_closed()
client.stop_retry()

# Client tags
client.add_tag("channel", "general")
targets = server.get_clients_by_tag("channel", "general")

# Rust engine switch (captured at each Server/Client initialization:
# construction, server.restart(), client reconnection)
disable_rust()  # force the pure-Python engine
enable_rust()   # re-enable the compiled Rust engine (when installed)
```

---

## ⚡ Rust-powered hot path

Veltix 3.0.0 introduces a Rust-powered hot path for message parsing, compilation, and buffering.

Benchmarks against the Python fallback:

- **+30% throughput** under 100-client stress (138k msg/s)
- **-31% P99 latency**
- **-49% steadier FPS ticks** (tick stdev 0.175 ms vs 0.343 ms)
- **+20% burst send throughput**

The engine is picked at runtime: `disable_rust()` forces the pure-Python fallback, `enable_rust()`
re-enables the compiled engine (see `veltix.network._rust.rust_enabled()`). The choice is captured
when a `Server` / `Client` is (re)initialized - construction, `server.restart()`, client reconnection.

> Results are workload-dependent and were measured on Veltix 3.0.0 (Python 3.14.7, loopback).

---

## Backend Comparison: Threading vs Async

Veltix lets you switch between two socket backends via `SocketCore`. Pick the one that fits your use case.

| Criteria              | Threading (`SocketCore.THREADING`)           | Async (`SocketCore.ASYNC`)                     |
|-----------------------|----------------------------------------------|------------------------------------------------|
| **Model**             | One thread per client                        | Single-threaded event loop (selectors)         |
| **Best for**          | Simple apps, < 50 clients, predictable loads | High concurrency, 100+ clients, variable loads |
| **Concurrent stress** | ~51k msg/s                                   | **~108k msg/s (2.1x)**                         |
| **Idle memory**       | 60.8 KB server + 111 KB per client           | **≈0 server (noise floor) + ~80 KB per client** |
| **Latency**           | **0.041 ms**                                 | 0.050 ms                                       |
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

> Benchmarked on Python 3.14.7 : 12-core CPU, 30.5 GB RAM, Linux (loopback).
> On v3.0.0+ the message hot path runs in Rust - see [Rust-powered hot path](#rust-powered-hot-path) for the
> Rust engine vs pure-Python fallback numbers.

| Metric                             | Threading       | Async            |
|------------------------------------|-----------------|------------------|
| Concurrent stress (100 clients)    | 51,505 msg/s    | **108,084 msg/s (2.1x)** |
| Burst throughput                   | 64,158 / 48,558 | 60,358 / 46,351  |
| Idle server memory                 | 60.8 KB         | ≈0 (noise floor) |
| Per client memory (avg)            | 111 KB          | ≈80 KB (noisy)   |
| Average latency                    | 0.041 ms        | 0.050 ms         |
| FPS simulation (64 players @ 64Hz) | 4,489 msg/s     | 4,490 msg/s      |

Full benchmark details, methodology, and how to run them yourself : [PERFORMANCE.md](PERFORMANCE.md)

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
| High-level API         |   ✓   |    ✗    |     ~     |   ✗    |
| Zero dependencies      |   ✓   |    ✓    |    ✓     |   ✗    |
| No async required      |   ✓   |    ✓    |    ✗     |   ✗    |
| Message framing        |   ✓   |    ✗    |    ✗     |    ~    |
| Message integrity      |   ✓   |    ✗    |    ✗     |   ✗    |
| Automatic handshake    |   ✓   |    ✗    |    ✗     |   ✗    |
| Request/Response       |   ✓   |    ✗    |     ~     |   ✓    |
| Message routing        |   ✓   |    ✗    |    ✗     |    ~    |
| Auto-reconnect         |   ✓   |    ✗    |     ~     |   ✓    |
| Non-blocking callbacks |   ✓   |    ✗    |    ✓     |   ✓    |
| Built-in ping/pong     |   ✓   |    ✗    |    ✗     |   ✗    |
| Client tags            |   ✓   |    ✗    |    ✗     |   ✗    |
| Swappable backends     |   ✓   |    ✗    |    ✗     |   ✗    |
| Integrated logger      |   ✓   |    ✗    |     ~     |   ✓    |
| Content decoding       |   ✓   |    ✗    |    ✗     |   ✗    |

> ✓ Built-in &nbsp;&nbsp; ~ Possible but requires manual setup &nbsp;&nbsp; ✗ Not provided (you implement it yourself)

---

## Built with Veltix

Projects using Veltix in production:

- A new project is under construction. It will be based on Veltix to replace the abandoned Nexo (LAN file transfer
  tool).

> Built something with Veltix ? [Open a PR](https://github.com/NytroxDev/Veltix/pulls)
> or [start a discussion](https://github.com/NytroxDev/Veltix/discussions) to add your project.

---

## In Development

What is being worked on right now:

- **Handshake hardening**: more robust handshake handling, from per-step timeouts to cleaner version negotiation and
  failure recovery.
- **Performance optimization**: now that framing/parse/compile run in Rust, pushing the remaining hot-path overhead
  further. See [PERFORMANCE.md](PERFORMANCE.md).

> Experimental work lands on dedicated branches and only merges once fully validated.

---

## Documentation

- [Full documentation](docs/index.md)
- [Request-ID Correlation design](docs/design/request-id-correlation.md)
- [FAQ](FAQ.md)
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
