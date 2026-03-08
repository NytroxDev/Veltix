# Veltix

**A modern, lightweight TCP networking library for Python** — simple enough for beginners, solid enough for production.

[![PyPI](https://img.shields.io/pypi/v/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![Python](https://img.shields.io/pypi/pyversions/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![License](https://img.shields.io/github/license/NytroxDev/Veltix?cacheSeconds=300)](https://github.com/NytroxDev/Veltix/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/personalized-badge/veltix?period=total&units=NONE&left_color=BLACK&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/veltix)

---

## Why Veltix?

Working directly with Python's `socket` module forces you to handle framing, integrity, threading, and protocol design
from scratch. Veltix handles all of that for you.

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

## Features

- ✅ **Zero dependencies** — pure Python stdlib
- ✅ **Automatic handshake** — HELLO/HELLO_ACK with version compatibility check
- ✅ **Message integrity** — SHA-256 on every message
- ✅ **Message routing** — `@server.route(MY_TYPE)` / `@client.route(MY_TYPE)` decorators
- ✅ **Auto-reconnect** — configurable retry with `DisconnectState` callbacks
- ✅ **Non-blocking callbacks** — thread pool for all user callbacks
- ✅ **Request/Response** — `send_and_wait()` with timeout
- ✅ **Built-in ping/pong** — bidirectional latency measurement
- ✅ **Performance modes** — `LOW` / `BALANCED` / `HIGH` presets
- ✅ **Production-ready logger** — colorized, file-rotating, thread-safe

## Quick links

- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quickstart.md)
- [API Reference](api/server.md)
- [Changelog](changelog.md)
- [GitHub](https://github.com/NytroxDev/Veltix)
