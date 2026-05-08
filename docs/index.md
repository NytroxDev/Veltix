# Veltix

**A modern, lightweight TCP networking library for Python** — simple enough for beginners, solid enough for production.

[![PyPI](https://img.shields.io/pypi/v/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![Python](https://img.shields.io/pypi/pyversions/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![License](https://img.shields.io/github/license/NytroxDev/Veltix?cacheSeconds=300)](https://github.com/NytroxDev/Veltix/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/personalized-badge/veltix?period=total&units=NONE&left_color=BLACK&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/veltix)

---

## Why Veltix?

Working directly with Python's `socket` module or `asyncio` forces you to manage framing, concurrency, error handling,
and protocol design from scratch. Heavier frameworks like Twisted introduce steep learning curves and large dependency
trees.

Veltix sits in between: a focused library that handles the hard parts — connection management, message integrity,
threading, handshake, routing, and request correlation — while keeping the API surface small and the codebase readable.

```python
# Server
server = Server(ServerConfig(host="0.0.0.0", port=8080))
server.set_callback(Events.ON_RECV, lambda client, msg: print(msg.content.decode()))
server.start()

# Client
client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))
client.connect()  # handshake done automatically
client.get_sender().send(Request(MY_TYPE, b"Hello!"))
```

**Designed for:**

- Developers who want structured TCP communication without dealing with `asyncio` internals
- Teams that need a maintainable, dependency-free networking layer in production
- Real-time applications and simulations
- Rapid prototyping of client/server applications
- Custom protocol experimentation

---

## Features

- **Simple API** — Get a working client/server in under 30 lines
- **High Performance** — 110k+ messages/second, 0.007ms average latency
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

To run the benchmark suite yourself:

```bash
# Run all benchmarks
python -m veltix.benchmark

# Run specific benchmarks
python -m veltix.benchmark --only memory latency burst

# Save results to JSON for sharing
python -m veltix.benchmark --save results.json
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

### v1.6.4 — ClientsManager & Socket Restructure *(May 2026)* ✓

- Centralized `ClientsManager` with thread-safe `ClientEntry` (id + info + buffer)
- Socket module restructured: `veltix/socket/` → `veltix/socket_core/`
- `_close_server_client()` now operates on `ClientEntry` instead of `ClientInfo`
- `close_client()` method with `ClientEntry` / int ID support
- Cleaner `BaseSocket` Protocol definition

### v1.6.3 — Benchmark Refactor *(April 2026)* ✓

- Full benchmark module refactor into a clean, reusable package (`veltix/benchmark/`)
- Extended result models with leak detection, tick accuracy, pipeline drain, and per-client throughput metrics
- Run via `python -m veltix.benchmark`

### v1.6.2 — Protocol Optimization & Stability *(April 2026)* ✓

- Optimized wire protocol (22-byte header, 4-byte request IDs, CRC32 integrity)
- Client module split (`config.py`, `disconnect.py`, `reconnect_handler.py`)
- Fixed reconnect flow on connection failures
- Official minimum runtime lowered to **Python 3.8+**

### v1.5.0 — Routing & Reconnect *(March 2026)* ✓

- Decorator-based message routing (`@server.route(MY_TYPE)`, `@client.route(MY_TYPE)`)
- Auto-reconnect with configurable retry and `DisconnectState` callbacks
- `PerformanceMode` presets for CPU/reactivity trade-off

### v1.4.0 — Handshake & Callbacks *(March 2026)* ✓

- HELLO/HELLO_ACK handshake with version compatibility check
- Thread pool for non-blocking callback execution
- Blocking `connect()` — safe to send immediately after connecting

### v1.6.0 — Socket Abstraction & Tags *(March 2026)* ✓

- `BaseSocket` Protocol — universal socket interface
- `SocketCore` enum — swappable socket backends with zero API changes
- `ClientInfo` tags — arbitrary metadata on connected clients
- Benchmark suite with JSON export

### v1.7.0 — Selectors *(June 2026)*

- `AsyncSocket` — selectors-based I/O, replaces one-thread-per-client
- Same API, 4–8× throughput improvement expected
- Switch via `SocketCore.ASYNC`

### v1.8.0 — Plugin System *(August 2026)*

- `VeltixBasePlugin` — extensible plugin architecture
- Permission system for plugin event access
- `server.register_plugin()` / `client.register_plugin()`

### v2.0.0 — Encryption *(September 2026)*

- End-to-end encryption: ChaCha20 + X25519 + Ed25519
- Automatic key exchange and perfect forward secrecy

### v3.0.0 — Rust Core *(2027)*

- PyO3 bindings, 10–100× throughput improvement
- `SocketCore.RUST` backend

---

## Quick links

- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quickstart.md)
- [Server Guide](guides/server.md)
- [Client Guide](guides/client.md)
- [API Reference](api/server.md)
- [Changelog](changelog.md)
- [GitHub](https://github.com/NytroxDev/Veltix)
- [PyPI](https://pypi.org/project/veltix)
- [Discord](https://discord.gg/NrEjSHtfMp)
