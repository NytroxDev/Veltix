# Veltix

> The high-level TCP library Python never had.

[![Lines of code](https://img.shields.io/endpoint?url=https://ghloc.vercel.app/api/NytroxDev/Veltix/badge)](https://ghloc.vercel.app/NytroxDev/Veltix)
[![PyPI](https://img.shields.io/pypi/v/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![Python](https://img.shields.io/pypi/pyversions/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![License](https://img.shields.io/github/license/NytroxDev/Veltix?cacheSeconds=300)](https://github.com/NytroxDev/Veltix/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/personalized-badge/veltix?period=total&units=NONE&left_color=BLACK&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/veltix)

Sync, thread-friendly, zero dependencies : TCP done right.
Veltix handles framing, threading, handshake, routing, and reconnection
so you can focus on your application logic.

```python
@server.route(CHAT)
def on_chat(response: Response, client: ClientInfo):
    print(f"{client.addr}: {response.content.decode()}")
```

---

## Why Veltix?

Python's `socket` module is powerful but painful. You end up reimplementing
framing, threading, reconnection, and protocol design every single time.
Heavier alternatives like `asyncio` or `Twisted` solve this but force you into
async/await or steep learning curves.

Veltix sits in between :

- **No async required** : sync, thread-based, works like you expect
- **No boilerplate** : framing, handshake, routing, reconnect are built-in
- **No dependencies** : pure Python stdlib, zero install friction
- **FastAPI-style routing** : `@server.route(MY_TYPE)` instead of `if/elif` chains

**Designed for :** LAN tools, multiplayer games, real-time dashboards,
custom protocols, IPC, remote tooling, file transfer.

---

## Features

**Core**

- Zero dependencies : pure Python stdlib
- Binary protocol with CRC32 integrity verification
- Automatic HELLO/HELLO_ACK handshake with version compatibility
- Thread-safe callback execution : slow handlers never block reception

**API**

- FastAPI-style routing : `@server.route(MY_TYPE)` / `@client.route(MY_TYPE)`
- `send_and_wait()` : built-in request/response correlation with timeout
- Built-in ping/pong : bidirectional latency measurement
- Client tags : attach arbitrary metadata to connected clients

**Reliability**

- Auto-reconnect : configurable retry with `DisconnectState` callbacks
- `LOW` / `BALANCED` / `HIGH` performance mode presets
- Swappable socket backends via `SocketCore` (Threading now, Selectors in v1.7.0, Rust in v3.0.0)

**Developer Experience**

- Integrated logger : colorized, file-rotating, thread-safe
- 208 tests, CI on Python 3.8 / 3.10 / 3.12 / 3.14

---

## Performance

> Benchmarked on Python 3.14.5 : 12-core CPU, 30.5 GB RAM, Linux (loopback).

| Metric                          | Result                      |
|---------------------------------|-----------------------------|
| Concurrent stress (100 clients) | 38,985 msg/s : 100% success |
| Burst send                      | 52,377 msg/s                |
| Average latency                 | 0.006 ms                    |
| Idle server memory              | 212 KB                      |

Full details : [Performance](../PERFORMANCE.md)

---

## Quick links

- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quickstart.md)
- [Server Guide](guides/server.md)
- [Client Guide](guides/client.md)
- [Routing](guides/routing.md)
- [Auto-Reconnect](guides/reconnect.md)
- [API Reference](api/server.md)
- [Changelog](changelog.md)
- [GitHub](https://github.com/NytroxDev/Veltix)
- [PyPI](https://pypi.org/project/veltix)
- [Discord](https://discord.gg/jwjEV5eze7)