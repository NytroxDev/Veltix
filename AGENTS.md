# AGENTS.md - Veltix

Guidelines for AI coding agents working on the Veltix project.

## Project Overview

Veltix is a high-level TCP library for Python: sync, thread-friendly, zero dependencies.  
It handles framing, threading, handshake, routing, and reconnection.

- **Version:** 2.0.0b3
- **Python:** 3.8+
- **License:** MIT
- **Zero runtime dependencies:** pure stdlib only.

## Use Cases (When to Use Veltix)

Veltix is designed for projects that need **raw TCP communication** without the complexity of async frameworks or the
boilerplate of raw sockets.

**Perfect for:**

- **LAN tools:** file transfer, remote control, chat apps (e.g., [Nexo](https://github.com/NytroxDev/Nexo))
- **Multiplayer game servers:** real-time state sync, 64+ players at 64Hz tick rate
- **Real-time dashboards:** live data streaming between microservices
- **Custom protocols:** you control the message types, framing, and routing
- **IPC / inter-process communication:** lightweight process间通信 on localhost
- **Remote tooling:** SSH-like command execution, remote file management
- **IoT / embedded:** minimal memory footprint (21 KB idle), no heavy dependencies

**Not ideal for:**

- **HTTP/REST APIs:** use Flask, FastAPI, or Django REST Framework
- **Browser clients:** Veltix uses raw TCP, not WebSocket; use websockets or Socket.IO for browser apps
- **Async-first codebases:** Veltix is sync by design; if your whole project is async, use `asyncio` directly
- **Very high throughput (>100k msg/s per connection):** consider a compiled language for the hot path

**Key differentiator:** Veltix gives you FastAPI-style routing (`@server.route(MY_TYPE)`) over raw TCP, with built-in
framing, handshake, ping/pong, and reconnection: zero dependencies, zero boilerplate.

## Performance

> Benchmarked on Python 3.14.5: 12-core CPU, 30.5 GB RAM, Linux (loopback). All numbers are 5-run averages.

| Metric                             | Threading    | Async            |
|------------------------------------|--------------|------------------|
| Idle server memory                 | 20.8 KB      | 4 KB             |
| Per client memory (avg)            | 34.5 KB      | 12.4 KB          |
| Average latency                    | 0.033 ms     | 0.036 ms         |
| Burst send                         | 49,287 msg/s | 49,878 msg/s     |
| Burst receive                      | 39,517 msg/s | 39,909 msg/s     |
| Concurrent stress (100 clients)    | 32,297 msg/s | **82,937 msg/s** |
| FPS simulation (64 players @ 64Hz) | 4,490 msg/s  | 4,491 msg/s      |

Async stress throughput is **2.6x higher** than Threading under high concurrency.

## Tech Stack

| Tool           | Purpose                 | Config                                        |
|----------------|-------------------------|-----------------------------------------------|
| hatchling      | Build/packaging         | `pyproject.toml`                              |
| pytest         | Testing                 | `[tool.pytest.ini_options]` in pyproject.toml |
| pytest-cov     | Code coverage           | `[tool.coverage.*]` in pyproject.toml         |
| pytest-asyncio | Async test support      |                                               |
| ruff           | Linting & formatting    | `[tool.ruff.*]` in pyproject.toml             |
| mypy           | Static type checking    | `[tool.mypy]` in pyproject.toml               |
| mkdocs         | Documentation           | `mkdocs.yml`                                  |
| mkdocstrings   | Auto-generated API docs | Google-style docstrings                       |

## Project Structure

```
src/veltix/
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
│   ├── request.py       # Request class
│   ├── response.py      # Response class (content decoding: .text, .json, .is_json, .is_text)
│   ├── parser.py        # MessageParser — parse raw bytes into Response objects
│   ├── sender.py        # Sender, Mode
│   ├── types.py         # MessageType, MessageTypeRegistry
│   ├── system_types.py  # PING, PONG
│   ├── constants.py     # MAGIC, HEADER_SIZE, REQUEST_ID_SIZE, HEADER_STRUCT
│   ├── flags.py         # MessageFlag (IntFlag, internal)
│   ├── id_allocator.py  # IDAllocator, ClientAllocator (internal)
│   └── message_buffer.py
├── handler/             # Request routing & callbacks
│   ├── request_handler.py   # RequestHandler
│   ├── handshake_handler.py # HandshakeHandler
│   ├── callback_executor.py # CallbackExecutor (thread pool)
│   ├── rules.py             # PingRule, PendingRequestRule, RouteRule, etc.
│   └── rules_manager.py     # RulesManager, MessageContext, Rule
├── socket_core/         # Swappable socket backends
│   ├── core.py          # SocketCore enum (THREADING, ASYNC)
│   ├── base_socket.py   # BaseSocket
│   ├── threading_socket.py
│   ├── async_socket.py
│   ├── version.py       # __version__ = "2.0.0b3"
│   └── managers/
│       └── clients_manager.py
├── internal/            # Internal helpers
│   ├── bus.py           # VeltixBus (wraps Avyra EventBus)
│   ├── events.py        # Event enums (ServerEvent, ClientEvent, …)
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
├── _vendor/             # Vendored third-party libs
│   └── avyra/           # EventBus library (Avyra v1.0.0, Python 3.8 compat)
├── benchmark/           # CLI benchmarking suite (optional: pip install veltix[benchmark])
├── exceptions.py        # VeltixError hierarchy
└── __init__.py          # Public API exports
tests/
├── conftest.py              # Shared fixtures
├── test_callback_executor.py
├── test_client_server.py
├── test_client_tags.py
├── test_clients_manager.py
├── test_compatibility.py
├── test_error_handling.py
├── test_handshake.py
├── test_id_system.py
├── test_logger.py
├── test_logger_detail.py
├── test_message_buffer.py
├── test_message_type.py
├── test_network_internal.py
├── test_ping_pong.py
├── test_protocol.py
├── test_reconnect.py
├── test_request.py
├── test_response.py
├── test_routing.py
├── test_rules_unit.py
├── test_send_and_wait.py
├── test_sender.py
├── test_server_advanced.py
├── test_socket_core.py
├── test_socket_core_unit.py
├── test_utils.py
└── test_writer.py
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

from ..internal.events import ServerEvent
from ..network.request import Request

if TYPE_CHECKING:
    from ..network.types import MessageType
```

### Naming

| Element           | Convention  | Example              |
|-------------------|-------------|----------------------|
| Classes           | PascalCase  | `ServerConfig`       |
| Functions/methods | snake_case  | `send_and_wait()`    |
| Private methods   | `_` prefix  | `_handle_message()`  |
| Constants         | UPPER_SNAKE | `HEADER_SIZE`        |
| Enums             | PascalCase  | `class Events(Enum)` |
| Enum members      | UPPER_SNAKE | `Events.ON_RECV`     |
| Type variables    | PascalCase  | `T`, `ResponseT`     |
| Module variables  | snake_case  | `_id_lock`           |

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
- `BaseSocket` was refactored from `Protocol` to `ABC` in v1.8.1 — use `abstractmethod` for base class contracts that
  need stronger inheritance guarantees and slot-sharing.
- Avoid deep inheritance trees. Prefer composition.

### Logger & VeltixBus

Internal modules use `VeltixBus` for structured observability. A `Logger` singleton is auto-subscribed
to `LogEvent.*` so all `bus.*()` calls produce log output. Prefer the bus in new code:

```python
from ..logger.core import Logger
from ..internal.bus import VeltixBus

# Via bus (preferred for internal modules — emits structured events)
self.bus = VeltixBus()
self.bus.debug("Some message")
self.bus.error("Something went wrong: %s", error)

# Direct Logger (still works, auto-subscribed to bus)
self._logger = Logger.get_instance()
self._logger.debug("Some message")
```

Levels (same for both): `trace`, `debug`, `info`, `success`, `warning`, `error`, `critical`.

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
mypy src/veltix/
```

Both `ruff` and `mypy` must pass cleanly in CI.

## Key Patterns to Follow

### Adding a new MessageType

```python
from veltix import MessageType

MY_TYPE = MessageType("my_type")
```

Codes: 0-199 system, 200-9999 user, 10000+ plugins.

### Adding a route

```python
@server.route(MY_TYPE)
def on_my_type(client: ClientInfo, response: Response) -> None:
    ...
```

### Adding a new Rule

Inherit from `Rule` (in `handler/rules_manager.py`), implement `can_handle` and `handle`, then add to `ALL_RULES` list
in `handler/rules.py`.

### Adding a new event

Add a member to the appropriate event enum in `internal/events.py` (`ServerEvent`, `ClientEvent`,
`MessageEvent`, `ProtocolEvent`, `ErrorEvent`, `LogEvent`, or `ReconnectEvent`). Do NOT add to
the old `Events` enum (kept for backward compat only, to remove in v3.0).

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
- **Wire protocol changes** must be registered in the COMPATIBILITY table (`internal/compatibility.py`).
- **Backward compatibility** within a minor series is preferred but not guaranteed; breaking changes must bump minor and
  update COMPATIBILITY.

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

1. **Version consistency check:** `src/veltix/internal/version.py` must match `pyproject.toml`.
2. **Tests:** run on Python 3.8, 3.10, 3.12, 3.14 with `pytest`.

All pushed branches and PRs run through CI.

## Public API Reference

The public API is defined in `veltix/__init__.py`. Anything not listed in `__all__` is private and subject to change.

### Core Classes

#### `Server(config: ServerConfig)`

```python
from veltix import Server, ServerConfig

server = Server(ServerConfig(host="0.0.0.0", port=8080))
server.start()  # Non-blocking, starts accept loop in thread

# Callback style
server.on_recv(callback)  # func(client: ClientInfo, response: Response)
server.on_connect(callback)  # func(client: ClientInfo)
server.on_disconnect(callback)  # func(client: ClientInfo)

# Structured event bus (v1.9.0+)
from veltix.internal.events import ServerEvent

server.bus.subscribe(ServerEvent.ON_CONNECT, callback)
server.bus.subscribe(ServerEvent.ON_DISCONNECT, callback)


@server.route(MY_TYPE)  # Decorator: func(client, response)
def on_msg(client: ClientInfo, response: Response) -> None: ...


server.send(request, client)  # -> bool (convenience)
server.broadcast(request)  # -> bool (all clients)
server.broadcast(request, except_clients=[client])  # -> bool (exclude)
server.send_and_wait(request, client, timeout=5.0)  # -> Optional[Response]
server.ping_client(client, timeout=5.0)  # -> Optional[float] (latency ms)
server.close_client(client)  # -> bool
server.close_all()  # stop server + disconnect all
server.wait_until_closed()  # block until close_all()
server.restart()  # stop + start
server.clients  # -> list[ClientInfo]
server.get_clients_by_tag(tag, value=None)  # -> list[ClientInfo]
server.bus  # -> VeltixBus
```

#### `Client(config: ClientConfig)`

```python
from veltix import Client, ClientConfig

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080, retry=3, retry_delay=1.0))
client.connect()  # Blocks until handshake done -> bool

# Callback style
client.on_recv(callback)  # func(response: Response)
client.on_connect(callback)  # func()
client.on_disconnect(callback)  # func(state: DisconnectState)

# Structured event bus (v1.9.0+)
from veltix.internal.events import ClientEvent

client.bus.subscribe(ClientEvent.ON_CONNECT, callback)
client.bus.subscribe(ClientEvent.ON_DISCONNECT, callback)


@client.route(MY_TYPE)  # Decorator: func(response)
def on_msg(response: Response) -> None: ...


client.send(request)  # -> bool (convenience)
client.send_and_wait(request, timeout=5.0)  # -> Optional[Response]
client.ping_server(timeout=5.0)  # -> Optional[float] (latency ms)
client.disconnect()  # -> bool
client.stop_retry()  # cancel pending reconnection
client.retry(max_=None)  # force reconnection attempts
client.wait_until_closed()  # block until disconnect
client.bus  # -> VeltixBus
```

### Configuration

#### `ServerConfig`

```python
@dataclasses.dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    buffer_size: int = BufferSize.SMALL  # 1024 bytes
    max_connection: int = -1  # -1 = unlimited
    max_message_size: int = 10 * 1024 * 1024  # 10 MB
    handshake_timeout: float = 5.0
    max_workers: int = 4
    socket_core: SocketCore = SocketCore.ASYNC
    id_window: int = 30000  # unique IDs per direction per server
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
    retry: int = 0  # 0 = no reconnect
    retry_delay: float = 1.0
    socket_core: SocketCore = SocketCore.ASYNC
```

### Network Protocol

#### `Request(_type, content=None, *, text=None, json=None, request_id=None)`

Exactly one payload argument (`content`, `text`, or `json`) is required.

```python
from veltix import Request

req = Request(MY_TYPE, b"hello")  # raw bytes
req = Request(MY_TYPE, text="hello")  # UTF-8 encoded automatically
req = Request(MY_TYPE, json={"key": "val"})  # JSON serialized automatically
req.request_id  # Optional[int] — auto-allocated by Sender if None
req.compile()  # -> bytes (wire format)
req.respond(response)  # copy request_id from response for correlation
```

`request_id` is keyword-only: `Request(MY_TYPE, b"data", request_id=42)`.

#### `Response` (dataclass)

```python
@dataclasses.dataclass
class Response:
    type: MessageType
    content: bytes
    request_id: int  # public int property (uint16)

    # Lazy cached decoding properties:
    response.text  # -> str (UTF-8, cached, raises InvalidContentError)
    response.json  # -> Any (parsed JSON, cached, raises InvalidContentError)
    response.is_text  # -> bool (safe check, no exception)
    response.is_json  # -> bool (safe check, no exception)
```

#### `Sender`

```python
from veltix import Sender, Mode

sender.send(request)  # -> bool (CLIENT mode)
sender.send(request, client=socket)  # -> bool (SERVER mode)
sender.broadcast(request, list_of_clients)  # -> bool
sender.broadcast(request, list_of_clients, except_clients=[...])
```

#### `MessageType(code, name=None, description=None)`

```python
from veltix import MessageType

MY_TYPE = MessageType("my_type")
```

Code ranges: **0-199** system, **200-9999** user, **10000-65535** plugins.

#### System Types (pre-registered)

```python
from veltix import PING, PONG
# PING = MessageType(0, "ping")
# PONG = MessageType(1, "pong")
```

#### `MessageBuffer`

```python
from veltix.network.message_buffer import MessageBuffer

buf = MessageBuffer(max_message_size=10 * 1024 * 1024)
buf.add_data(raw_bytes)  # feed TCP stream data
buf.extract_messages()  # -> list[Response]
buf.clear()
```

### Client Info & Tags

#### `ClientInfo`

```python
client.ip  # -> str
client.port  # -> int
client.addr  # -> tuple[str, int]
client.conn  # -> BaseSocket
client.tags  # -> dict[str, Any]

client.add_tag(name, value=None)  # -> bool (False if exists)
client.has_tag(name)  # -> bool
client.has_all_tags(names)  # -> bool
client.has_any_tags(names)  # -> bool
client.get_tag(name)  # -> Optional[Any]
client.remove_tag(name)  # -> bool
client.clear_tags()
```

### Events

```python
from veltix.internal.events import ServerEvent, ClientEvent

# Server events
ServerEvent.ON_CONNECT  # client connected
ServerEvent.ON_DISCONNECT  # client disconnected
ServerEvent.STARTED  # server started
ServerEvent.STOPPED  # server stopped

# Client events
ClientEvent.ON_CONNECT  # connected to server
ClientEvent.ON_DISCONNECT  # disconnected from server
```

#### Structured Event Bus (events accessible via `veltix.internal.events`)

```python
from veltix.internal.events import ServerEvent, ClientEvent, MessageEvent, ProtocolEvent, ErrorEvent, LogEvent,

ReconnectEvent

# Subscribe via server.bus / client.bus
server.bus.subscribe(ServerEvent.ON_CONNECT, callback)

# Server lifecycle
ServerEvent.ON_DISCONNECT
ServerEvent.STARTED
ServerEvent.STOPPED
ServerEvent.CLIENT_REJECTED

# Client lifecycle
ClientEvent.ON_CONNECT
ClientEvent.ON_DISCONNECT
ClientEvent.CONNECTING
ClientEvent.DISCONNECTING
ClientEvent.TAG_ADDED
ClientEvent.TAG_REMOVED
ClientEvent.TAG_CLEARED

# Message flow
MessageEvent.RECEIVED
MessageEvent.SENT
MessageEvent.ROUTED
MessageEvent.UNHANDLED
MessageEvent.PENDING_REGISTERED
MessageEvent.PENDING_SATISFIED
MessageEvent.PENDING_TIMEOUT
MessageEvent.ROUTE_REGISTERED
MessageEvent.ROUTE_UNREGISTERED

# Protocol
ProtocolEvent.PING
ProtocolEvent.PONG
ProtocolEvent.HANDSHAKE_START
ProtocolEvent.HANDSHAKE_DONE
ProtocolEvent.HANDSHAKE_FAIL

# Errors
ErrorEvent.NETWORK
ErrorEvent.HANDLER
ErrorEvent.CALLBACK
ErrorEvent.SEND
ErrorEvent.ACCEPT
ErrorEvent.CONNECTION_REFUSED

# Logging (auto-subscribed to Logger)
LogEvent.TRACE
LogEvent.DEBUG
LogEvent.INFO
LogEvent.SUCCESS
LogEvent.WARNING
LogEvent.ERROR
LogEvent.CRITICAL

# Reconnection
ReconnectEvent.ATTEMPT
ReconnectEvent.FAIL
ReconnectEvent.SUCCESS
ReconnectEvent.CANCELLED
```

### Socket Backends

```python
from veltix import SocketCore

SocketCore.THREADING  # thread-per-client
SocketCore.ASYNC  # selectors-based (default)
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

BufferSize.SMALL  # 1 KB
BufferSize.MEDIUM  # 8 KB
BufferSize.LARGE  # 64 KB
BufferSize.HUGE  # 1 MB
```

### Version Compatibility

```python
from veltix import Version, COMPATIBILITY

v = Version(2, 0, 0)
v2 = Version.from_str("v2.0.0")
v.is_compatible(v2)  # -> Optional[bool] (True/False/None)
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
logger.get_stats()  # -> {LogLevel: count}
logger.configure(new_config)  # reconfigure at runtime
Logger.reset_instance()  # for testing
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

encode_utf8("hello")  # -> b"hello"
decode_utf8(b"hello")  # -> "hello"
encode_json({"key": 1})  # -> b'{"key": 1}'
decode_json(b'{"key": 1}')  # -> {"key": 1}
format_bytes(148_000)  # -> "144.5 KB"
```

### Exceptions

```python
from veltix import VeltixError, MessageTypeError, RequestError, SenderError


class VeltixError(Exception): ...  # base


class MessageTypeError(VeltixError): ...  # invalid message type


class RequestError(VeltixError): ...  # parse/compile failure


class SenderError(VeltixError): ...  # send failure


class NetworkError(VeltixError): ...  # network operation failure


class TimeoutError(VeltixError): ...  # operation timeout


class InvalidContentError(VeltixError): ...  # content decode failure (response.text / response.json)
```

### Complete Examples

#### Example 1: Chat server + client

**`chat_server.py`**

```python
from veltix import Server, ServerConfig, ClientInfo, Response, MessageType, Request

CHAT = MessageType("chat")
server = Server(ServerConfig(host="0.0.0.0", port=8080))


@server.route(CHAT)
def on_chat(client: ClientInfo, response: Response) -> None:
    print(f"[{client.ip}] {response.text}")
    server.broadcast(Request(CHAT, response.text), except_clients=[client])


server.on_connect(lambda c: print(f"+ {c.addr}"))
server.on_disconnect(lambda c: print(f"- {c.addr}"))
server.start()
input("Press Enter to stop...\n")
server.close_all()
```

**`chat_client.py`**

```python
from veltix import Client, ClientConfig, Response, MessageType, Request
import threading
import time

CHAT = MessageType("chat")
client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))


@client.route(CHAT)
def on_chat(response: Response) -> None:
    print(f"\n[{client.config.server_addr}]: {response.text}")


client.connect()


def _input_loop() -> None:
    while True:
        msg = input()
        if msg.lower() == "/quit":
            client.disconnect()
            break
        client.send(Request(CHAT, text=msg))


threading.Thread(target=_input_loop, daemon=True).start()

try:
    while client.is_connected:
        time.sleep(0.1)
except (KeyboardInterrupt, SystemExit):
    client.disconnect()
```

#### Example 2: Request/Response (RPC pattern)

```python
from veltix import Server, ServerConfig, Client, ClientConfig, MessageType, Request, Response, ClientInfo

ECHO = MessageType("echo")
server = Server(ServerConfig(port=8080))


@server.route(ECHO)
def on_echo(client: ClientInfo, response: Response) -> None:
    server.send(Request(ECHO, response.content), client)


server.start()

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))
client.connect()

resp = client.send_and_wait(Request(ECHO, text="Hello RPC!"), timeout=3.0)
if resp:
    print(f"Got: {resp.text}")  # "Got: Hello RPC!"

client.disconnect()
server.close_all()
```

#### Example 3: Broadcast with tags

```python
from veltix import MessageType, Request, Server, ServerConfig, ClientInfo, Response

CHANNEL_JOIN = MessageType("channel_join")
CHANNEL_MSG = MessageType("channel_msg")
server = Server(ServerConfig(port=8080))


@server.route(CHANNEL_JOIN)
def on_join(client: ClientInfo, response: Response) -> None:
    channel = response.text
    client.add_tag("channel", channel)
    print(f"{client.ip} joined channel '{channel}'")


@server.route(CHANNEL_MSG)
def on_msg(client: ClientInfo, response: Response) -> None:
    channel = client.get_tag("channel")
    if channel:
        targets = server.get_clients_by_tag("channel", channel)
        server.broadcast(
            Request(CHANNEL_MSG, response.text), except_clients=[client]
        )
```
