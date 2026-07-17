# Veltix

> Python TCP, without the boilerplate.

[![Lines of code](https://img.shields.io/endpoint?url=https://ghloc.vercel.app/api/NytroxDev/Veltix/badge)](https://ghloc.vercel.app/NytroxDev/Veltix)
[![PyPI](https://img.shields.io/pypi/v/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![Python](https://img.shields.io/pypi/pyversions/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![License](https://img.shields.io/github/license/NytroxDev/Veltix?cacheSeconds=300)](https://github.com/NytroxDev/Veltix/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/personalized-badge/veltix?period=total&units=NONE&left_color=BLACK&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/veltix)

Sync, thread-friendly, zero dependencies : TCP done right.
Veltix handles framing, threading, handshake, routing, and reconnection
so you can focus on your application logic.

**Mature & tested** : 571+ tests · CI on Python 3.8-3.14 · 12+ releases

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

**Echo server with raw sockets (41 lines):**

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

---

## Features

**Core**

- Zero dependencies : pure Python stdlib
- Binary protocol with CRC32 integrity verification
- Automatic JSON raw-socket handshake with version compatibility
- Thread-safe callback execution : slow handlers never block reception

**API**

- FastAPI-style routing : `@server.route(MY_TYPE)` / `@client.route(MY_TYPE)`
- `send_and_wait()` : built-in request/response correlation with timeout
- Text & JSON payloads : `Request(MY_TYPE, text="hello")` / `Request(MY_TYPE, json={"k": "v"})`
- Content decoding : `response.text`, `response.json`, `response.is_json`, `response.is_text`
- Convenience send : `server.send()` / `client.send()` — no need to touch `Sender` directly
- Built-in ping/pong : bidirectional latency measurement
- Client tags : attach arbitrary metadata to connected clients

**Reliability**

- Auto-reconnect : configurable retry with `DisconnectState` callbacks
- `SMALL` / `MEDIUM` / `LARGE` buffer size presets
- Swappable socket backends via `SocketCore` (Threading or Async/Selectors)

**Developer Experience**

- Integrated logger : colorized, file-rotating, thread-safe
- 571 tests, CI on Python 3.8 / 3.10 / 3.12 / 3.14

---

## Performance

> Benchmarked on Python 3.14.5 : 12-core CPU, 30.5 GB RAM, Linux (loopback).

| Metric                          | Threading       | Async           |
|---------------------------------|-----------------|-----------------|
| Concurrent stress (100 clients) | 32,297 msg/s    | **82,937 msg/s**|
| Burst send                      | 49,287 msg/s    | 49,878 msg/s    |
| Average latency                 | 0.033 ms        | 0.036 ms        |
| Idle server memory              | 20.8 KB         | 4 KB            |

Full details : [Performance](../PERFORMANCE.md)

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

## Quick links

- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quickstart.md)
- [Server Guide](guides/server.md)
- [Client Guide](guides/client.md)
- [Routing](guides/routing.md)
- [Auto-Reconnect](guides/reconnect.md)
- [Migration Guide](guides/migration.md)
- [API Reference](api/server.md)
- [Changelog](changelog.md)
- [GitHub](https://github.com/NytroxDev/Veltix)
- [PyPI](https://pypi.org/project/veltix)
- [Discord](https://discord.gg/gz8K369a6p)
