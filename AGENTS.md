# AGENTS.md - Veltix

Guidelines for AI coding agents working on the Veltix project.

## Project Overview

Veltix is a high-level TCP library for Python: sync, thread-friendly, zero dependencies.  
It handles framing, threading, handshake, routing, and reconnection.

- **Version:** 1.7.0
- **Python:** 3.8+
- **License:** MIT
- **Zero runtime dependencies:** pure stdlib only.

## Use Cases (When to Use Veltix)

Veltix is designed for projects that need **raw TCP communication** without the complexity of async frameworks or the boilerplate of raw sockets.

**Perfect for:**
- **LAN tools:** file transfer, remote control, chat apps (e.g., [Nexo](https://github.com/NytroxDev/Nexo))
- **Multiplayer game servers:** real-time state sync, 64+ players at 64Hz tick rate
- **Real-time dashboards:** live data streaming between microservices
- **Custom protocols:** you control the message types, framing, and routing
- **IPC / inter-process communication:** lightweight进程间通信 on localhost
- **Remote tooling:** SSH-like command execution, remote file management
- **IoT / embedded:** minimal memory footprint (46 KB idle), no heavy dependencies

**Not ideal for:**
- **HTTP/REST APIs:** use Flask, FastAPI, or Django REST Framework
- **Browser clients:** Veltix uses raw TCP, not WebSocket; use websockets or Socket.IO for browser apps
- **Async-first codebases:** Veltix is sync by design; if your whole project is async, use `asyncio` directly
- **Very high throughput (>100k msg/s per connection):** consider a compiled language for the hot path

**Key differentiator:** Veltix gives you FastAPI-style routing (`@server.route(MY_TYPE)`) over raw TCP, with built-in framing, handshake, ping/pong, and reconnection: zero dependencies, zero boilerplate.

## Tech Stack

| Tool        | Purpose               | Config                                     |
|-------------|-----------------------|--------------------------------------------|
| setuptools  | Build/packaging       | `pyproject.toml`                           |
| pytest      | Testing               | `[tool.pytest.ini_options]` in pyproject.toml |
| pytest-cov  | Code coverage         | `[tool.coverage.*]` in pyproject.toml      |
| pytest-asyncio | Async test support |                                             |
| ruff        | Linting & formatting  | `[tool.ruff.*]` in pyproject.toml          |
| mypy        | Static type checking  | `[tool.mypy]` in pyproject.toml            |
| mkdocs      | Documentation         | `mkdocs.yml`                               |
| mkdocstrings | Auto-generated API docs | Google-style docstrings                  |

## Project Structure

```
veltix/
├── client/              # TCP client & reconnect
│   ├── client.py        # Client class
│   ├── config.py        # ClientConfig dataclass
│   ├── disconnect.py    # DisconnectState, DisconnectReason
│   └── reconnect_handler.py
├── server/              # TCP server
│   ├── server.py        # Server class
│   ├── config.py        # ServerConfig dataclass
│   └── client_info.py   # ClientInfo dataclass
├── network/             # Protocol layer
│   ├── request.py       # Request, Response, MAGIC, HEADER_SIZE
│   ├── sender.py        # Sender, Mode
│   ├── types.py         # MessageType, MessageTypeRegistry
│   ├── system_types.py  # PING, PONG, HELLO, HELLO_ACK
│   └── message_buffer.py
├── handler/             # Request routing & callbacks
│   ├── request_handler.py   # RequestHandler
│   ├── handshake_handler.py # HandshakeHandler
│   ├── callback_executor.py # CallbackExecutor (thread pool)
│   ├── rules.py             # PingRule, HelloRule, RouteRule, etc.
│   └── rules_manager.py     # RulesManager, MessageContext, Rule
├── socket_core/         # Swappable socket backends
│   ├── core.py          # SocketCore enum (THREADING, ASYNC)
│   ├── base_socket.py   # BaseSocket, SocketEvents
│   ├── threading_socket.py
│   ├── async_socket.py
│   └── managers/
│       └── clients_manager.py
├── internal/            # Internal helpers
│   ├── events.py        # Events enum
│   ├── buffer_size.py   # BufferSize enum
│   ├── compatibility.py # Version, COMPATIBILITY
│   ├── mode.py          # Mode enum
│   └── network.py
├── logger/              # Singleton logger (thread-safe, colorized, rotation)
│   ├── core.py          # Logger class
│   ├── config.py        # LoggerConfig dataclass
│   ├── levels.py        # LogLevel enum
│   ├── formatter.py     # Log formatting
│   └── writer.py        # File rotation writer
├── utils/               # Small utilities
│   ├── encoding.py      # encode/decode utf8 & json
│   └── format_size.py   # format_bytes
├── benchmark/           # CLI benchmarking suite
├── exceptions.py        # VeltixError hierarchy
├── version.py           # __version__ = "1.7.0"
└── __init__.py          # Public API exports
tests/
├── conftest.py          # Shared fixtures
├── test_client_server.py
├── test_routing.py
├── test_reconnect.py
├── test_ping_pong.py
├── test_send_and_wait.py
├── test_protocol.py
├── test_message_buffer.py
├── test_logger.py
└── ...
docs/
├── index.md
├── getting-started/
├── guides/
└── api/
```

## Coding Conventions

### Python & Syntax

- Target **Python 3.8:** no walrus operator (`:=`), no `match`/`case`, no `|` union syntax.
- Use `from __future__ import annotations` for forward references.
- Line length: **100** characters.
- Indentation: **4 spaces**.
- Quotes: **double quotes** (`"` not `'`), except when unnecessary escaping occurs.

### Typing

```python
from typing import Callable, Optional, Union

# Use Optional[X], not X | None
# Use Union[X, Y], not X | Y
# Use TYPE_CHECKING guards for type-only imports
if TYPE_CHECKING:
    from ...network.types import MessageType
```

- `disallow_untyped_defs = true`: all public methods MUST have type annotations.
- `strict_equality = true`
- Return type `-> None` on every function/method that returns nothing.

### Docstrings

**Google style:** every public class and method:

```python
def send_message(self, data: bytes, client: ClientInfo) -> bool:
    """
    Send a message to a specific client.

    Args:
        data: Message bytes to send.
        client: Target client information.

    Returns:
        True if send succeeded, False otherwise.
    """
```

No docstrings on private methods (`_*`). No comments inside functions unless the logic is genuinely non-obvious.

### Imports

Order (separated by blank line):
1. Python stdlib
2. Third-party (none currently: zero deps)
3. Veltix internal (`from ..module import ...`)
4. `TYPE_CHECKING` block

No `import *`. Use explicit relative imports within the package.

```python
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Callable, Optional

from ..internal.events import Events
from ..network.request import Request

if TYPE_CHECKING:
    from ..network.types import MessageType
```

### Naming

| Element              | Convention     | Example                |
|----------------------|----------------|------------------------|
| Classes              | PascalCase     | `ServerConfig`         |
| Functions/methods    | snake_case     | `send_and_wait()`      |
| Private methods      | `_` prefix     | `_handle_message()`    |
| Constants            | UPPER_SNAKE    | `HEADER_SIZE`          |
| Enums                | PascalCase     | `class Events(Enum)`   |
| Enum members         | UPPER_SNAKE    | `Events.ON_RECV`       |
| Type variables       | PascalCase     | `T`, `ResponseT`       |
| Module variables     | snake_case     | `_id_lock`             |

### Dataclasses

Prefer `@dataclasses.dataclass` for configuration and data-holder classes.

```python
import dataclasses

@dataclasses.dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8080
```

### Slots

Use `__slots__` on hot-path classes for memory efficiency:

```python
class MessageType:
    __slots__ = ("code", "name", "description")
```

### Inheritance & Protocols

- Use `Protocol` from `typing` for structural subtyping (e.g., `ClientContext`).
- Avoid deep inheritance trees. Prefer composition.

### Logger

Always use the singleton logger:

```python
from ..logger.core import Logger

self._logger = Logger.get_instance()
self._logger.debug("Some message")
self._logger.error("Something went wrong: %s", error)
```

Levels: `trace`, `debug`, `info`, `success`, `warning`, `error`, `critical`.

### Thread Safety

- Use `threading.Lock` for shared mutable state.
- Use `threading.Event` for signaling between threads.
- Use `queue.Queue` for producer-consumer patterns.
- All user callbacks execute in a thread pool (`CallbackExecutor`), not in the receiving thread.

## Testing Conventions

- **Framework:** pytest
- **Config:** `[tool.pytest.ini_options]` in `pyproject.toml`
- **Fixtures:** in `tests/conftest.py`
- **Test file naming:** `test_*.py` or `*_test.py`
- **Test function naming:** `test_*`
- **Test classes:** `Test*`
- **Markers:** `slow`, `integration`, `unit`

Key fixtures (conftest.py):
- `cleanup_after_test`: autouse, clears `MessageTypeRegistry`, waits 0.3s for thread cleanup.
- `reset_logger`: resets logger singleton before/after test.
- `test_message_type`: creates a unique `MessageType` per test.
- `socket_core_backend`: parametrizes over `THREADING` and `ASYNC` backends.

Run all tests:
```bash
python -m pytest tests/ -v --tb=short
```

Run with coverage:
```bash
python -m pytest tests/ --cov=veltix --cov-report=term
```

Run specific test:
```bash
python -m pytest tests/test_routing.py -v
```

No test should depend on external servers or network access.

## Linting & Type Checking

```bash
# Lint
ruff check .

# Format
ruff format . --check

# Type check
mypy veltix/
```

Both `ruff` and `mypy` must pass cleanly in CI.

## Key Patterns to Follow

### Adding a new MessageType

```python
from veltix import MessageType

MY_TYPE = MessageType(code=300, name="my_type")
```

Codes: 0-199 system, 200-499 user, 500+ plugins.

### Adding a route

```python
@server.route(MY_TYPE)
def on_my_type(client: ClientInfo, response: Response) -> None:
    ...
```

### Adding a new Rule

Inherit from `Rule` (in `handler/rules_manager.py`), implement `can_handle` and `handle`, then add to `ALL_RULES` list in `handler/rules.py`.

### Adding a new event

Add member to `Events` enum in `internal/events.py` and add to the `events` list.

### Adding a new exception

Inherit from `VeltixError` in `exceptions.py`.

```python
class MyNewError(VeltixError):
    """Description."""
```

## Constraints

- **NO new runtime dependencies.** Pure stdlib only.
- **NO async public API.** Internally async is OK (AsyncSocket), but the public API is synchronous.
- **Support Python 3.8+:** no syntax or stdlib features from 3.9+.
- **Thread safety:** all shared state must be protected.
- **Type hints** required on all public symbols.
- **Google-style docstrings** required on all public symbols.
- **100% backward compatibility** within the same major version.

## Git & Commit

- **Single-line commits only.**
- Use conventional commits: `feat:`, `fix:`, `refactor:`, `chore:`, `test:`, `docs:`, `perf:`.
- Optional scope in parentheses: `feat(server):`, `fix(async_socket):`.
- Lowercase after the colon, no period at the end.
- Never amend a pushed commit.
- Never force push.

Examples:
```
feat(protocol): implement MAGIC bytes integrity check
fix: handle BlockingIOError in accept loop
refactor: extract _network_recv utility
docs: update README with benchmark results
test: parametrize integration tests over socket backends
```

## CI Pipeline

Defined in `.github/workflows/ci.yml`:

1. **Version consistency check:** `veltix/version.py` must match `pyproject.toml`.
2. **Tests:** run on Python 3.8, 3.10, 3.12, 3.14 with `pytest`.

All pushed branches and PRs run through CI.

## Public API Reference

The public API is defined in `veltix/__init__.py`. Anything not listed in `__all__` is private and subject to change.

### Core Classes

#### `Server(config: ServerConfig)`
```python
from veltix import Server, ServerConfig

server = Server(ServerConfig(host="0.0.0.0", port=8080, socket_core=SocketCore.THREADING))
server.start()                                      # Non-blocking, starts accept loop in thread
server.set_callback(Events.ON_RECV, callback)       # func(client: ClientInfo, response: Response)
server.set_callback(Events.ON_CONNECT, callback)    # func(client: ClientInfo)
server.set_callback(Events.ON_DISCONNECT, callback) # func(client: ClientInfo)

@server.route(MY_TYPE)                              # Decorator: func(client, response)
def on_msg(client: ClientInfo, response: Response) -> None: ...

server.get_sender()                                 # -> Sender
server.send_and_wait(request, client, timeout=5.0)  # -> Optional[Response]
server.ping_client(client, timeout=5.0)             # -> Optional[float] (latency ms)
server.ping_client_async(client, callback, timeout) # non-blocking ping
server.close_client(client)                         # -> bool
server.close_all()                                  # stop server + disconnect all
server.clients                                      # -> list[ClientInfo]
server.get_all_clients_sockets()                    # -> list[BaseSocket]
server.get_clients_sockets_by_tag(tag, value=None)  # -> list[BaseSocket]
```

#### `Client(config: ClientConfig)`
```python
from veltix import Client, ClientConfig

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080, retry=3, retry_delay=1.0))
client.connect()                                    # Blocks until handshake done -> bool
client.set_callback(Events.ON_RECV, callback)       # func(response: Response)
client.set_callback(Events.ON_CONNECT, callback)    # func()
client.set_callback(Events.ON_DISCONNECT, callback) # func(state: DisconnectState)

@client.route(MY_TYPE)                              # Decorator: func(response, client=None)
def on_msg(response: Response) -> None: ...

client.get_sender()                                 # -> Sender
client.send_and_wait(request, timeout=5.0)          # -> Optional[Response]
client.ping_server(timeout=5.0)                     # -> Optional[float] (latency ms)
client.disconnect()                                 # -> bool
client.stop_retry()                                 # cancel pending reconnection
client.retry(max_=None)                             # force reconnection attempts
```

### Configuration

#### `ServerConfig`
```python
@dataclasses.dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    buffer_size: int = BufferSize.SMALL              # 1024 bytes
    max_connection: int = -1                         # -1 = unlimited
    max_message_size: int = 10 * 1024 * 1024         # 10 MB
    handshake_timeout: float = 5.0
    max_workers: int = 4
    socket_core: SocketCore = SocketCore.ASYNC
```

#### `ClientConfig`
```python
@dataclasses.dataclass
class ClientConfig:
    server_addr: str = "127.0.0.1"
    port: int = 8080
    buffer_size: int = BufferSize.SMALL
    max_message_size: int = 10 * 1024 * 1024
    handshake_timeout: float = 5.0
    max_workers: int = 4
    retry: int = 0                                   # 0 = no reconnect
    retry_delay: float = 1.0
    socket_core: SocketCore = SocketCore.ASYNC
```

### Network Protocol

#### `Request(_type, content, request_id=None)`
```python
from veltix import Request

req = Request(MY_TYPE, b"hello")                     # auto-generates request_id
req = Request(MY_TYPE, b"hello", request_id=b"\x00"*4)
req.compile()                                        # -> bytes (wire format)
Request.parse(data, max_message_size=10MB)           # -> Response (static)
```

#### `Response` (dataclass)
```python
@dataclasses.dataclass
class Response:
    type: MessageType
    content: bytes
    hash: bytes
    request_id: bytes
```

#### `Sender`
```python
from veltix import Sender, Mode

sender.send(request)                                 # -> bool (CLIENT mode)
sender.send(request, client=socket)                  # -> bool (SERVER mode)
sender.broadcast(request, list_of_clients)           # -> bool
sender.broadcast(request, list_of_clients, except_clients=[...])
```

#### `MessageType(code, name=None, description=None)`
```python
from veltix import MessageType

MY_TYPE = MessageType(code=300, name="my_type")
```

Code ranges: **0-199** system, **200-499** user, **500+** plugins.

#### System Types (pre-registered)
```python
from veltix import PING, PONG, HELLO, HELLO_ACK
# PING    = MessageType(0, "ping")
# PONG    = MessageType(1, "pong")
# HELLO   = MessageType(10, "hello")
# HELLO_ACK = MessageType(11, "hello_ack")
```

#### `MessageBuffer`
```python
from veltix.network.message_buffer import MessageBuffer

buf = MessageBuffer(max_message_size=10*1024*1024)
buf.add_data(raw_bytes)                              # feed TCP stream data
buf.extract_messages()                               # -> list[Response]
buf.clear()
```

### Client Info & Tags

#### `ClientInfo`
```python
client.ip                                           # -> str
client.port                                         # -> int
client.addr                                         # -> tuple[str, int]
client.conn                                         # -> BaseSocket
client.tags                                         # -> dict[str, Any]

client.add_tag(name, value=None)                    # -> bool (False if exists)
client.has_tag(name)                                # -> bool
client.has_all_tags(names)                          # -> bool
client.has_any_tags(names)                          # -> bool
client.get_tag(name)                                # -> Optional[Any]
client.remove_tag(name)                             # -> bool
client.clear_tags()
```

### Events

```python
from veltix import Events

Events.ON_RECV       # "on_recv"
Events.ON_CONNECT    # "on_connect"
Events.ON_DISCONNECT # "on_disconnect"
```

### Socket Backends

```python
from veltix import SocketCore

SocketCore.THREADING # thread-per-client (default)
SocketCore.ASYNC     # selectors-based (v1.7.0+)
# SocketCore.RUST    # planned v3.0.0
```

### Disconnect System

```python
from veltix import DisconnectState, DisconnectReason

DisconnectReason.SERVER_CLOSED
DisconnectReason.ERROR
DisconnectReason.MANUAL

@dataclasses.dataclass
class DisconnectState:
    permanent: bool
    attempt: int
    retry_max: int
    reason: DisconnectReason
```

### Buffer Presets

```python
from veltix import BufferSize

BufferSize.SMALL   # 1 KB
BufferSize.MEDIUM  # 8 KB
BufferSize.LARGE   # 64 KB
BufferSize.HUGE    # 1 MB
```

### Version Compatibility

```python
from veltix import Version, COMPATIBILITY

v = Version(1, 7, 0)
v2 = Version.from_str("v1.6.6")
v.is_compatible(v2)          # -> Optional[bool] (True/False/None)
```

### Logger

```python
from veltix import Logger, LoggerConfig, LogLevel

logger = Logger.get_instance()
# or with config: Logger.get_instance(LoggerConfig(level=LogLevel.DEBUG))

logger.trace("msg")
logger.debug("msg")
logger.info("msg")
logger.success("msg")
logger.warning("msg")
logger.error("msg")
logger.critical("msg")

logger.set_level(LogLevel.WARNING)
logger.enable()
logger.disable()
logger.get_stats()              # -> {LogLevel: count}
logger.configure(new_config)    # reconfigure at runtime
Logger.reset_instance()         # for testing
```

#### `LoggerConfig`
```python
@dataclasses.dataclass
class LoggerConfig:
    level: LogLevel = LogLevel.INFO
    enabled: bool = True
    use_colors: bool = True
    show_timestamp: bool = True
    show_caller: bool = True
    show_level: bool = True
    file_path: Optional[Path] = None
    file_rotation_size: int = 10 * 1024 * 1024
    file_backup_count: int = 5
```

#### Log Levels
| Level      | Severity |
|------------|----------|
| `TRACE`    | 5        |
| `DEBUG`    | 10       |
| `INFO`     | 20       |
| `SUCCESS`  | 25       |
| `WARNING`  | 30       |
| `ERROR`    | 40       |
| `CRITICAL` | 50       |

### Utility Functions

```python
from veltix import encode_utf8, decode_utf8, encode_json, decode_json, format_bytes

encode_utf8("hello")       # -> b"hello"
decode_utf8(b"hello")      # -> "hello"
encode_json({"key": 1})    # -> b'{"key": 1}'
decode_json(b'{"key": 1}') # -> {"key": 1}
format_bytes(148_000)      # -> "144.5 KB"
```

### Exceptions

```python
from veltix import VeltixError, MessageTypeError, RequestError, SenderError

class VeltixError(Exception): ...          # base
class MessageTypeError(VeltixError): ...   # invalid message type
class RequestError(VeltixError): ...       # parse/compile failure
class SenderError(VeltixError): ...        # send failure
class NetworkError(VeltixError): ...       # network operation failure
class TimeoutError(VeltixError): ...       # operation timeout
```

### Quick-Start Patterns

**Server with route:**
```python
from veltix import Server, ServerConfig, ClientInfo, Response, MessageType

CHAT = MessageType(code=200, name="chat")
server = Server(ServerConfig(port=8080))

@server.route(CHAT)
def on_chat(client: ClientInfo, response: Response) -> None:
    print(f"{client.ip}: {response.content.decode()}")

server.start()
```

**Client with reconnect:**
```python
from veltix import Client, ClientConfig, Response

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080, retry=5))
client.set_callback(Events.ON_RECV, lambda r: print(r.content.decode()))
client.connect()
client.get_sender().send(Request(CHAT, b"Hello!"))
```

**Request/Response pattern:**
```python
req = Request(MY_TYPE, b"ping")
resp = client.send_and_wait(req, timeout=3.0)
if resp:
    print(resp.content)
```
