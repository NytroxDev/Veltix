# Veltix

> The high-level TCP library Python never had.

[![Lines of code](https://img.shields.io/endpoint?url=https://ghloc.vercel.app/api/NytroxDev/Veltix/badge)](https://ghloc.vercel.app/NytroxDev/Veltix)
[![PyPI](https://img.shields.io/pypi/v/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![Python](https://img.shields.io/pypi/pyversions/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![License](https://img.shields.io/github/license/NytroxDev/Veltix?cacheSeconds=300)](https://github.com/NytroxDev/Veltix/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/personalized-badge/veltix?period=total&units=NONE&left_color=BLACK&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/veltix)
[![Security Policy](https://img.shields.io/badge/security-policy-blue)](SECURITY.md)

Sync, thread-friendly, zero dependencies : TCP done right.  
Veltix handles framing, threading, handshake, routing, and reconnection  
so you can focus on your application logic.

**52k msg/s** • **0.006ms latency** • **212KB idle** • **100% success rate**

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

## Built with Veltix

Projects using Veltix in production:

- **[Nexo](https://github.com/NytroxDev/Nexo)** : Fast LAN file transfer tool CLI + GUI.
  Uses Veltix's TCP server, client tags, route decorators, and `send_and_wait()` for
  reliable chunked file transfers with concurrent connection handling.

> Built something with Veltix ? [Open a PR](https://github.com/NytroxDev/Veltix/pulls)
> or [start a discussion](https://github.com/NytroxDev/Veltix/discussions) to add your project.

---

## Why Veltix

Python's `socket` module is powerful but painful. You end up reimplementing
framing, threading, reconnection, and protocol design every single time.
Heavier alternatives like `asyncio` or `Twisted` solve this but force you into
async/await or steep learning curves.

Veltix sits in between:

- **No async required** : sync, thread-based, works like you expect
- **No boilerplate** : framing, handshake, routing, reconnect are built-in
- **No dependencies** : pure Python stdlib, zero install friction
- **FastAPI-style routing** : `@server.route(MY_TYPE)` instead of `if/elif` chains

```python
# This is all you need to get a working server
@server.route(CHAT)
def on_chat(response: Response, client: ClientInfo):
    print(f"{client.addr}: {response.content.decode()}")
```

**Designed for:** LAN tools, multiplayer games, real-time dashboards,
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

> Benchmarked on Python 3.14.5 — 12-core CPU, 30.5 GB RAM, Linux (loopback).

| Metric                             | Result                                |
|------------------------------------|---------------------------------------|
| Concurrent stress (100 clients)    | 38,985 msg/s — 100% success           |
| Burst throughput                   | 52,377 msg/s send / 41,496 msg/s recv |
| Average latency                    | 0.006 ms                              |
| Idle server memory                 | 212 KB                                |
| FPS simulation (64 players @ 64Hz) | 4,488 msg/s — 100% success            |

Full benchmark details, methodology, and how to run them yourself : [PERFORMANCE.md](PERFORMANCE.md)
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
from veltix import Server, ServerConfig, ClientInfo, Response, MessageType, Request, Events

CHAT = MessageType(code=200, name="chat")

server = Server(ServerConfig(host="0.0.0.0", port=8080))
sender = server.get_sender()


def on_message(client: ClientInfo, response: Response):
    print(f"[{client.addr[0]}] {response.content.decode()}")
    sender.broadcast(Request(CHAT, response.content), server.get_all_clients_sockets())


server.set_callback(Events.ON_RECV, on_message)
server.start()

input("Press Enter to stop...")
server.close_all()
```

**Client:**

```python
from veltix import Client, ClientConfig, Response, MessageType, Request, Events

CHAT = MessageType(code=200, name="chat")

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))

client.set_callback(Events.ON_RECV, lambda r: print(f"Server: {r.content.decode()}"))
client.connect()

client.get_sender().send(Request(CHAT, b"Hello Server!"))
input("Press Enter to disconnect...")
client.disconnect()
```

```bash
python server.py
python client.py  # In a separate terminal
```

---

## Roadmap

### v1.6.6 : Version Compatibility & Reconnect Stability *(May 2026)* : Released

`Version` class, reconnect stability fixes, +111 tests, CI on Python 3.8-3.14

### v1.6.8 : Architecture Refactor *(May 2026)* : Released

`ClientContext` Protocol, Rules system for `RequestHandler`, README rewrite

### v1.6.9 : Reconnect Stability & Cleanup *(June 2026)* : Released

8 bug fixes across reconnect path + code quality cleanups

### v1.7.0 : Selectors *(June 2026)* : Planned

`AsyncSocket` : selectors-based I/O, same API, 4-8x throughput improvement

[Full roadmap](ROADMAP.md)

---

## Comparison

| Feature                | Veltix | `socket` | `asyncio` | Twisted |
|------------------------|:------:|:--------:|:---------:|:-------:|
| Simple API             |   ✓    |    ✗     |     ~     |    ✗    |
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

---

## Documentation

- [Full documentation](docs/README.md)
- [Advanced features](docs/ADVANCED.md)
- [Migration guide](docs/MIGRATION.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Examples](examples/)

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request.

- Bug reports : [Open an issue](https://github.com/NytroxDev/Veltix/issues)
- Discussions : [Join the Discord](https://discord.gg/jwjEV5eze7)
- Pull requests : Follow the contribution guide

---

## License

MIT License : see [LICENSE](LICENSE) for details.

---

## Links

- GitHub : [NytroxDev/Veltix](https://github.com/NytroxDev/Veltix)
- PyPI : [pypi.org/project/veltix](https://pypi.org/project/veltix)
- Documentation : https://nytroxdev.github.io/Veltix/
- Discord : [discord.gg/jwjEV5eze7](https://discord.gg/jwjEV5eze7)