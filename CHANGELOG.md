# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.6.6] - 2026-05-14

### Added

- **`Version` class** in `veltix.internal.compatibility` : now exported publicly as `veltix.Version`
    - `Version.from_str("v1.6.6")` parses version strings with optional `v` prefix
    - `version.is_compatible(other)` performs a lookup-based compatibility check returning `True`, `False`, or `None` (
      unknown version)
    - Hashable, usable as dict key in the compatibility table
    - `__str__` returns `"1.6.6"`, `__repr__` returns `"Version(1.6.6)"`

- **`COMPATIBILITY` table** in `veltix.internal.compatibility` : now exported publicly as `veltix.COMPATIBILITY`
    - Declarative `dict[Version, list[Version]]` : each version explicitly declares its compatible peers
    - Default policy: strict self-compatibility (`v1.6.6` is only compatible with `v1.6.6`)
    - Replaces the previous hardcoded equality check in `HandshakeHandler`

- **Comprehensive test coverage** bringing the total test suite to 208 tests
    - `test_compatibility.py` : 17 tests covering `Version` parsing, hashing, compatibility checks, and the
      `COMPATIBILITY` table
    - `test_client_tags.py` : 22 tests covering the full `ClientInfo` tag API (`add_tag`, `has_tag`, `has_all_tags`,
      `has_any_tags`, `get_tag`, `remove_tag`, `clear_tags`)
    - `test_clients_manager.py` : 20 tests covering `ClientsManager` and `ClientEntry` (CRUD, tag filtering, thread
      safety)
    - `test_utils.py` : 22 tests covering `format_bytes`, `encode_utf8`, `decode_utf8`, `encode_json`, `decode_json`
    - `test_sender.py` : expanded from 2 to 18 tests (send, broadcast, error handling, mock socket)
    - `test_error_handling.py` : expanded from 2 to 16 tests (exception hierarchy, parse errors, network failures)

- **GitHub Actions CI workflow** (`.github/workflows/ci.yml`)
    - Version consistency check: blocks push if `version.py` and `pyproject.toml` are out of sync
    - Test matrix on Python 3.8, 3.10, 3.12, and 3.14 in parallel
    - Ruff lint check on every push

### Changed

- **`HandshakeHandler` version check refactored** to use `Version` and `COMPATIBILITY`
    - Removed `split_version()` and `_check_version()` string-based methods
    - Handler now stores `self.version = Version.from_str(__version__)` on init
    - `_decode_hello()` now returns a `Version` object instead of a raw string
    - Version mismatch logs now display structured `Version` representations

- **Lazy `TYPE_CHECKING` imports** introduced across 7 modules (`handshake_handler.py`, `request_handler.py`,
  `sender.py`, `clients_manager.py`, `network.py`, `formatter.py`, `writer.py`) to resolve circular import issues at
  runtime

- **`Writer.write()`** simplified exception suppression using `contextlib.suppress(Exception)` instead of bare
  try/except pass

- **`pytest.ini`** moved from `tests/pytest.ini` to the project root for correct `pythonpath` resolution

- **Reconnect tests** (`test_reconnect.py`): Replaced arbitrary `time.sleep()` calls with polling helpers
  (`_wait_for_disconnect`, `_wait_for_connect`) that wait for actual state transitions. Used dynamic port
  allocation (`_find_free_port`) to eliminate port conflicts. Reduced timeout ceilings from 30s to 3s.
  Adjusted `test_retry_delay_is_respected` assertion from `>= 0.6s` to `>= 0.3s` (1 sleep between 2 attempts,
  not before each).

### Fixed

- **`Server.close_client(id_=0)`** was silently ignored because `if id_:` treated `0` as falsy, skipping the socket
  lookup entirely. Now correctly uses `if id_ is not None`

- **`ThreadingSocket.bind()`** now returns `bool` instead of `None`; returns `False` when the socket is already running

- **`ThreadingSocket._create_client_instance()`** was missing the `client_manager` attribute, causing
  `entry.info.conn.close()` to silently crash with `AttributeError` when the server tried to close a client
  connection. The underlying TCP socket was never closed — the client only detected the disconnection when
  Python's garbage collector eventually freed the file descriptor, causing unpredictable delays (2–3s) and
  flaky disconnect detection in tests.

- **`ReconnectHandler.reconnect_loop()`** retry delay was applied *before* each connection attempt instead of
  *between* failures. This wasted `retry_delay` time even when the server was immediately available. The loop
  now attempts the first connection immediately and only sleeps after a failed attempt.

- **`ReconnectHandler.stop_retry()`** could not interrupt an in-progress `time.sleep(retry_delay)` wait.
  Replaced `time.sleep()` with `threading.Event.wait(timeout=...)` so `stop_retry()` cancels the delay
  instantly via `Event.set()`.

- **`ThreadingSocket.close_all()`** closed client connections before closing the listening socket,
  creating a window where a reconnecting client could attach to the dying server's still-open
  listener. The connection appeared to succeed (TCP handshake completed) but the server's handler
  thread was already stopped, so no handshake occurred — `ON_CONNECT` never fired. Now closes the
  listening socket first, so rogue reconnections get a clean `ConnectionRefusedError`.

## [1.6.5] - 2026-05-11

### Added

- **`close_client()` method** in `Server` — forcefully close a specific client connection
    - Accepts `ClientInfo` or client ID (int) via `id_` parameter
    - Both paths route through `socket.close_client()` — socket closed + `ON_DISCONNECT` triggered
- **`get_clients_by_tag()` method** in `ClientsManager` — thread-safe tag-based client filtering
    - Accepts a tag name and optional value for exact matching
    - Returns `list[ClientEntry]`
- **`to_sockets()` method** in `ClientsManager` — converts `list[ClientEntry]` to `list[BaseSocket]`
- **`get_clients_by_tag()` method** in `Server` — high-level wrapper over `ClientsManager.get_clients_by_tag()`
    - Returns sockets directly — no access to internal `socket.client_manager` required

### Fixed

- **`close_client()` via ID** in previous implementation called `client_manager.remove_client()` directly — socket was
  not closed and `ON_DISCONNECT` was never triggered. Now correctly routes through `socket.close_client()`

## [1.6.4] - 2026-05-07

### Added

- **`ClientsManager`** — new centralized, thread-safe client management layer (`veltix/socket_core/managers/`)
    - `ClientEntry` dataclass with `id`, `info` (ClientInfo), and `buffer` (MessageBuffer)
    - `add_client()`, `remove_client()`, `get_client()`, `get_all_clients()`, `count()` methods
    - `iter_on_clients()` for safe concurrent iteration
    - `has_client_id()` / `has_client_info()` for efficient lookup
- **`close_client()` method** in `ThreadingSocket` — accepts `ClientEntry` or client ID (int)

### Changed

- **Socket module restructured**: `veltix/socket/` → `veltix/socket_core/`
    - All imports updated across client, server, and internal modules
- **`ThreadingSocket`**: Replaced manual client list + buffer dict with `ClientsManager`
    - Removed `_clients_lock`, `_buffers_lock`, `_client_buffers` — unified through `ClientEntry.buffer`
    - `_handle_server_client()` now operates on `client_id` (int) and resolves via `ClientsManager`
    - `_close_server_client()` accepts `ClientEntry` instead of `ClientInfo`
- **`Server.clients` property**: Now returns `list[ClientEntry]` (access client data via `.info`)
- **`BaseSocket` Protocol**: Cleanly declares `client_manager` as class attribute (no `__init__` body)

### Internal

- `veltix/socket/` → `veltix/socket_core/` — directory renamed
- `veltix/socket_core/managers/clients_manager.py` — new module
- `benchmark.py` cleanup: removed from VCS tracking, root-level `benchmark.py` dropped
- Tests aligned with new `ClientEntry` API (`server.clients[0].info.*`)

## [1.6.3] - 2026-04-21

### Added

- **Benchmark module refactor** — split into a clean, reusable package under `veltix/benchmark/`
    - `benchmark/__init__.py` — module docstring and public entry points
    - `benchmark/__main__.py` — `python -m veltix.benchmark` entry point
    - `benchmark/cli.py` — CLI argument parsing and main orchestrator
    - `benchmark/config.py` — message types, port constants, terminal width
    - `benchmark/models.py` — `LatencyStats`, `MemoryResult`, `FpsResult`, `BurstResult`, `StressResult`
    - `benchmark/display.py` — terminal rendering and README-ready summary table
    - `benchmark/export.py` — JSON build/export for results
    - `benchmark/utils.py` — `ram_kb()`, `ram_mb()` helpers
    - `benchmark/benches/memory.py` — memory footprint benchmark with leak detection
    - `benchmark/benches/latency.py` — ping/pong latency with full statistics
    - `benchmark/benches/fps.py` — FPS server simulation with tick accuracy metrics
    - `benchmark/benches/burst.py` — burst throughput with pipeline drain metrics
    - `benchmark/benches/stress.py` — concurrent stress with per-client throughput

### Changed

- **`MemoryResult`**: Extended with per-client cost distribution (avg, min, max, median, stdev) and leak detection
    - Measures cost at both cold start (first 10 clients) and warm scale (10→50 clients)
    - Reports RSS after full teardown with explicit leak delta
- **`FpsResult`**: Extended with tick accuracy metrics (actual tick rate, avg/min/max/stdev tick duration, budget %,
  overrun count)
- **`BurstResult`**: Extended with pipeline drain latency percentiles and jitter
- **`StressResult`**: Extended with timing breakdown (send phase, drain time, time-to-first-recv) and per-client
  throughput distribution

### Internal

- `benchmark.py` removed from project root (replaced by the package)
- Entry point updated: `veltix-benchmark` now resolves to `benchmark.cli:main`

## [1.6.2] - 2026-04-12

### Added

- **Python 3.8 support**: Minimum supported runtime lowered to Python 3.8+
    - Packaging metadata updated (`requires-python >=3.8`)
    - Tooling targets aligned for Python 3.8 (Ruff, MyPy)
    - Type annotation compatibility pass across client/server modules
- **Client module split**:
    - `veltix/client/config.py` — `ClientConfig` dataclass
    - `veltix/client/disconnect.py` — `DisconnectReason`, `DisconnectState`
    - `veltix/client/reconnect_handler.py` — `ReconnectHandler` for retry logic
    - Cleaner boundaries between API, state models, and reconnect flow
- **Benchmark module relocation**: `benchmark.py` moved to `veltix/benchmark.py`

### Fixed

- **Client connect flow**:
    - Prevented false "connected" state when underlying socket connect fails
    - Connection refusal now fails fast instead of waiting full handshake timeout
- **Reconnect loop stability**:
    - Fixed reconnect recursion edge case that could stall reconnect tests
    - Restored backward-compatible internal `_try_reconnect` path used by tests
    - Fixed retry override bug in reconnect handler (`retry()` config update path)
- **Disconnect handling**:
    - Fixed missing `on_disconnect` attribute path on client
    - Improved disconnect event propagation and `is_connected` state updates
- **Server restart behavior in tests**:
    - Improved shutdown/join behavior in `ThreadingSocket` to avoid transient port reuse races

### Changed

- **Protocol format optimized**:
    - Header size reduced from 62 bytes to **22 bytes**
    - `request_id` reduced from UUID string (16-byte encoded UUID) to **4 raw bytes**
    - Payload integrity switched from **SHA-256** to **CRC32** (`4` bytes)
    - `Request.parse()` / `Request.compile()` updated to the new binary layout
- **Handshake compatibility policy**:
    - Version check is now strict on full `major.minor.patch` match
    - `1.4.3` and `1.4.5` are now considered incompatible
- **Core socket implementation refactor**:
    - `ThreadingSocket` now owns accept loop, client loop, framing, and callback dispatch integration
    - `RequestHandler`, `Sender`, `MessageBuffer`, and `network.recv()` streamlined around the new flow

### Breaking Changes

- `Request.request_id` and `Response.request_id` are now `bytes` (4 bytes), not UUID strings.
- Any code expecting textual UUID IDs must be migrated.
- Wire protocol changed (header/hash/request_id layout). v1.6.2 is **not wire-compatible** with <= v1.6.0 peers.

### Migration Guide

- Custom request id:
    - Before: `Request(T, b"x", request_id="my-id")`
    - After: `Request(T, b"x", request_id=b"\x01\x02\x03\x04")`
- Logging/display:
    - Before: `response.request_id[:8]`
    - After: `response.request_id.hex()[:8]`
- Mixed versions:
    - Upgrade client and server to v1.6.2 together.

- **Runtime version export**:
    - `veltix.version.__version__` now aligned to `1.6.2`

## [1.6.0] - 2026-03-14

### Added

- **Socket Abstraction Layer**: Universal socket interface via `BaseSocket` Protocol
    - `BaseSocket` — `typing.Protocol` defining the universal socket contract
    - `ThreadingSocket` — current threading implementation behind the abstraction
    - `SocketCore` enum — selects the socket backend at config time
    - `SocketCore.THREADING` — default, one thread per client (current behavior)
    - `SocketCore.ASYNC` — reserved for v1.7.0 (selectors-based)
    - `SocketCore.RUST` — reserved for v3.0.0 (Tokio via PyO3)
    - Switching backends requires zero changes to application code
    - `Server` and `Client` no longer import the `socket` module directly
- **Client Tags**: Arbitrary metadata on connected clients
    - `client.add_tag(name, value=None)` — attach a tag, returns `False` if already exists
    - `client.has_tag(name)` — check for a single tag
    - `client.has_all_tags(names)` — check all tags are present (AND)
    - `client.has_any_tags(names)` — check at least one tag is present (OR)
    - `client.get_tag(name)` — retrieve the value associated with a tag
    - `client.remove_tag(name)` — remove a tag, returns `False` if not found
    - `client.clear_tags()` — remove all tags
    - Tags are stored in a `dict[str, Any]` — O(1) lookup, minimal memory overhead
- **`veltix.utils`**: New public utilities module
    - `format_bytes(size)` — human-readable byte formatting (`148_000` → `"144.5 KB"`)
    - `encode_utf8(data)` — encode `str` or `bytes` to UTF-8 bytes
    - `decode_utf8(data)` — decode UTF-8 bytes to `str`
    - `encode_json(data)` — encode any object to JSON bytes
    - `decode_json(data)` — decode JSON bytes to Python object
    - All utilities exported from `veltix` directly
- **Benchmark JSON export**: `python benchmark.py --save results.json`
    - Saves full results with system info (Python version, CPU, RAM, OS)
    - Structured for future community leaderboard support

### Changed

- **`ServerConfig.max_connection`**: Default changed from `2` to `-1` (unlimited)
- **`ServerConfig` / `ClientConfig`**: New `socket_core` field (default: `SocketCore.THREADING`)
- **`ClientInfo`**: Migrated from manual `__slots__` to `@dataclasses.dataclass(slots=True)`
    - Fixes `ValueError: 'tags' in __slots__ conflicts with class variable`
    - `tags` field uses `dataclasses.field(default_factory=dict)`
- **`server/` module**: Split into `server.py`, `config.py`, `client_info.py`
    - `server.py` reduced from 630 lines to ~370 lines
    - Each file has a single responsibility
- **`utils/` → `internal/`**: Internal utilities moved to `veltix/internal/`
    - `veltix/utils/` is now the public utilities module
- **`Sender`**: Migrated from `socket.socket` to `BaseSocket`
    - `sendall()` replaced by `send()` — consistent with `BaseSocket` interface
- **`network.recv()`**: Accepts `BaseSocket` instead of `socket.socket`
    - `socket.timeout` replaced by built-in `TimeoutError`

### Fixed

- **`RuntimeError: cannot join current thread`**: Fixed in `Server.close_client()`
    - `close_client()` is often called from within the client thread itself
    - Added `thread != threading.current_thread()` guard before `join()`
    - Eliminated flood of error logs during `close_all()` with many clients

### Internal

- `veltix/socket/base_socket.py` — `BaseSocket` Protocol with `@runtime_checkable`
- `veltix/socket/threading_socket.py` — `ThreadingSocket` implementation
- `veltix/socket/core.py` — `SocketCore` enum
- `veltix/socket/__init__.py` — module exports
- `veltix/server/client_info.py` — `ClientInfo` with tags
- `veltix/server/config.py` — `ServerConfig`
- `veltix/utils/encoding.py` — encoding helpers
- `veltix/utils/format_size.py` — `format_bytes`

### Notes

- No breaking changes to public API
- Throughput slightly lower than v1.5.0 due to the `BaseSocket` abstraction layer overhead
- Performance will be recovered and exceeded in v1.7.0 with `SocketCore.ASYNC`

---

## [1.5.0] - 2026-03-07

### Added

- **Message Routing**: Decorator-based per-type message handlers
    - `@server.route(MY_TYPE)` and `@client.route(MY_TYPE)` decorators
    - Routes take priority over the global `on_recv` callback
    - `request_handler.register_route(type_, func)` and `unregister_route(type_)` for programmatic control
    - Route callbacks run in the thread pool — slow handlers never block the recv loop
    - Server route signature: `func(response: Response, client: ClientInfo)`
    - Client route signature: `func(response: Response, client=None)`
- **Auto-Reconnect**: Automatic reconnection on initial failure and mid-session disconnection
    - `ClientConfig.retry` — number of reconnection attempts (default: `0` = disabled)
    - `ClientConfig.retry_delay` — seconds between attempts (default: `1.0`)
    - `client.stop_retry()` — cancel pending retries, fires `on_disconnect(permanent=True)`
    - `client.retry(max=N)` — force a new attempt, optionally override `retry_max`
    - Reconnection preserves all registered callbacks and routes
- **DisconnectState**: Rich disconnect info passed to `on_disconnect` callback
    - `permanent: bool` — `True` when retries are exhausted or `stop_retry()` was called
    - `attempt: int` — current retry attempt number
    - `retry_max: int` — configured maximum
    - `reason: DisconnectReason` — `SERVER_CLOSED`, `ERROR`, or `MANUAL`
- **PerformanceMode**: Tunable timing presets for CPU/reactivity trade-off
    - `PerformanceMode.LOW` — socket timeout 1.0s, minimal CPU usage
    - `PerformanceMode.BALANCED` — socket timeout 0.5s, default
    - `PerformanceMode.HIGH` — socket timeout 0.1s, fast disconnection detection
    - `PerformanceMode.AUTO` — reserved for future dynamic adjustment
    - Configurable via `ServerConfig.performance_mode` and `ClientConfig.performance_mode`
- **BufferSize**: Enum presets for common buffer sizes
    - `BufferSize.SMALL` — 1KB (default)
    - `BufferSize.MEDIUM` — 8KB
    - `BufferSize.LARGE` — 64KB
    - `BufferSize.HUGE` — 1MB
    - `buffer_size` fields in `ServerConfig` / `ClientConfig` still accept any custom integer

### Changed

- **`on_disconnect` callback signature (Client)**: Now receives a `DisconnectState` argument
    - Before: `func()`
    - After: `func(state: DisconnectState)`
- **`network.recv()`**: Replaced `Optional[bytes]` return with `RecvResult`
    - `result.ok` — data received normally
    - `result.timed_out` — socket timeout, connection still alive
    - `result.disconnected` — peer closed or fatal error
    - Eliminates the ambiguity between timeout and real disconnection
- **`ServerConfig`**: Added `performance_mode` and `buffer_size` (now `BufferSize.SMALL` default)
- **`ClientConfig`**: Added `performance_mode`, `retry`, `retry_delay`, and `buffer_size` (now `BufferSize.SMALL`
  default)
- **`Server._handle_client()`**: Uses `RecvResult` — no more `if msg is None` ambiguity
- **`Client._handle_client()`**: Uses `RecvResult` — reconnect loop triggered on `result.disconnected`

### Breaking Changes

- **`on_disconnect` on Client** now receives a `DisconnectState` argument — update all existing callbacks:

```python
# Before (v1.4.0)
client.set_callback(Events.ON_DISCONNECT, lambda: print("Disconnected"))

# After (v1.5.0)
client.set_callback(Events.ON_DISCONNECT, lambda state: print(f"Disconnected — permanent={state.permanent}"))
```

### Migration Guide

#### v1.4.0 → v1.5.0

Update all `ON_DISCONNECT` callbacks on the client side to accept a `DisconnectState` argument.

New optional fields in `ClientConfig`:

- `retry` (default: `0`) — set to a positive integer to enable auto-reconnect
- `retry_delay` (default: `1.0`)
- `performance_mode` (default: `PerformanceMode.BALANCED`)
- `buffer_size` (default: `BufferSize.SMALL`)

New optional field in `ServerConfig`:

- `performance_mode` (default: `PerformanceMode.BALANCED`)
- `buffer_size` (default: `BufferSize.SMALL`)

### Internal

- `utils/performance_mode.py` — `PerformanceMode` enum and `PerformanceModeSettings` dataclass
- `utils/network.py` — `RecvResult`, `RecvStatus` replacing bare `Optional[bytes]`
- `handler/request_handler.py` — `_routes` dict, `register_route()`, `unregister_route()`
- Test suite expanded with `test_reconnect.py` (9 tests) and `test_routing.py` (10 tests)

---

## [1.4.0] - 2026-03-06

### Added

- **Handshake Protocol**: Automatic HELLO/HELLO_ACK exchange on every new connection
    - Server sends HELLO immediately after TCP connection is established
    - Client automatically responds with HELLO_ACK — fully transparent to the developer
    - Version compatibility check: `major.minor` must match, patch is ignored
    - Incompatible versions are rejected before any application message is exchanged
    - `ClientInfo.handshake_done` flag — always `True` when `on_connect` fires
- **Version Payload**: Version string embedded in HELLO and HELLO_ACK frames
    - Wire format: `[2B length][NB version UTF-8]`
    - Both sides log `server version=X` / `client version=X` on successful handshake
- **CallbackExecutor**: Thread pool for callback execution
    - `on_recv` callbacks now run in a dedicated `ThreadPoolExecutor`
    - Slow or blocking callbacks never delay message reception
    - Exceptions inside callbacks are caught and logged — they never crash the recv loop
    - Configurable via `max_workers` in `ServerConfig` / `ClientConfig` (default: 4)
- **Blocking `connect()`**: Client `connect()` now blocks until the handshake completes
    - Safe to send messages immediately after `connect()` returns
    - Configurable timeout via `ClientConfig.handshake_timeout` (default: 5.0s)
    - Returns `False` if handshake times out or connection is refused
- **`on_connect` / `on_disconnect` callbacks on Client**
    - `on_connect` fires after the handshake is complete, not at raw TCP connect time
    - `on_disconnect` fires when the server closes the connection
- **`version.py`**: Dedicated version module
    - `__version__` lives in `veltix/version.py` — importable without circular imports
    - `__init__.py` re-exports it as before

### Changed

- **`ServerConfig`**: Added `handshake_timeout` and `max_workers` fields
- **`ClientConfig`**: Added `handshake_timeout` and `max_workers` fields
- **`ClientInfo`**: Added `handshake_done: bool` slot — initialized to `False`, set to `True` after HELLO_ACK is
  received
- **`handle_client()` (Server)**: Handshake is now driven inside the recv loop
    - HELLO is sent before entering the loop
    - HELLO_ACK arrives naturally as the first message and is routed via `pending_requests`
    - No extra thread or blocking `wait()` call needed
- **`handle_client()` (Client)**: `on_connect` now fires after handshake, not at thread start
- **`RequestHandler`**: Callback dispatch now goes through `CallbackExecutor` instead of direct call

### Fixed

- Race condition where client could send application messages before server was ready to route them
- `on_connect` firing before handshake was complete

### Internal

- `HandshakeHandler` unit-tested independently (encode/decode, version check, compatibility)
- `CallbackExecutor` unit-tested independently (non-blocking submit, exception isolation)
- Test suite split from one 800-line file into 12 focused files (69 tests total)
- `HELLO` / `HELLO_ACK` system types: codes 10 and 11

### Notes

- No breaking changes to public API
- `on_connect` now fires slightly later (after handshake) — this is intentional and correct behavior

## [1.3.0] - 2026-02-24

### Added

- **RequestHandler Architecture**: Extracted message routing logic into dedicated handler class
    - Centralizes PING/PONG auto-response
    - Manages request/response correlation for `send_and_wait()`
    - Thread-safe message routing with proper locking
    - Works in both SERVER and CLIENT modes for consistent behavior
    - Unified message handling flow across the entire codebase
- **MessageBuffer**: Proper TCP stream handling to prevent message corruption
    - Accumulates incoming data and extracts complete messages
    - Handles partial messages and multiple concatenated messages
    - Prevents hash mismatch errors from fragmented TCP streams
    - Configurable max message size (default: 10MB) for DoS protection
- **Mode Enum**: New `Mode` enum in `utils.mode` for consistent mode handling
    - `Mode.SERVER` and `Mode.CLIENT` replace string-based mode checks
    - Shared across `Sender` and `RequestHandler` for consistency
    - Prevents circular import issues
- **Performance Optimizations**: Added `__slots__` throughout codebase
    - Reduced memory footprint: 148KB idle server, 52KB per client
    - Improved attribute access speed
    - Applied to Request, Response, MessageType, and config classes

### Changed

- **Server**: Now delegates all message handling to `RequestHandler`
    - Simplified `handle_client()` method (~70 lines removed)
    - Better error handling through centralized handler
    - Per-client MessageBuffer for proper stream handling
- **Client**: Now uses `RequestHandler` for consistent message processing
    - Same message handling logic as Server
    - Unified callback signature across Server and Client
    - Integrated MessageBuffer for reliable message parsing
- **send_and_wait()**: Fixed critical race condition
    - Request queue now registered BEFORE sending message
    - Prevents lost responses that arrive before queue registration
    - Consistent implementation for both Server and Client
- **Thread Management**:
    - Main server thread uses daemon mode
    - Improved shutdown sequence with proper socket closing
    - Better cleanup of client buffers on disconnect

### Fixed

- **CRITICAL**: Race condition in `send_and_wait()` where responses could be lost
- **CRITICAL**: TCP stream fragmentation causing hash mismatch errors
- MessageBuffer `__len__` causing falsy evaluation when empty
- Ping latency of 0.0ms incorrectly evaluated as failed (was counting as timeout)
- Thread synchronization during server shutdown
- Edge cases in PING/PONG auto-response
- Improved cleanup of pending requests on timeout

### Performance

Benchmarked on Python 3.14 • 12-core CPU • 30GB RAM • Linux

**Memory:**

- Idle server: 148 KB
- Per client: 52.4 KB
- 50 clients: 29.6 MB

**Latency (localhost):**

- Average: 0.012 ms
- P95: 0.000 ms
- P99: 1.000 ms

**Throughput:**

- Burst send: 67,236 msg/s
- Burst receive: 50,304 msg/s
- 100 concurrent clients: 40,402 msg/s
- Data throughput: 3.07 MB/s

**Real-world simulations:**

- 64 players @ 64 tick/s: 4,489 msg/s (100% success)
- 128 players @ 20 tick/s: 2,813 msg/s (100% success)

All tests achieved 100% message delivery with zero errors.

### Internal

- Moved `Mode` enum from `sender.py` to `utils.mode` to avoid circular imports
- Refactored message handling flow for better testability
- Added comprehensive logging throughout `RequestHandler` and `MessageBuffer`
- Improved type hints across Server, Client, RequestHandler, and MessageBuffer
- Better documentation with detailed docstrings

### Developer Experience

- Easier to understand code flow with separated concerns
- Better error messages with source attribution
- Consistent patterns across Server and Client
- Improved debugging with detailed trace logs
- TCP stream handling now transparent to users

### Notes

- No breaking changes to public API
- If you were directly accessing internal `_pending_requests`, this has moved to `RequestHandler`
- Main server thread uses daemon mode (will be replaced with selectors in v1.6.0)

## [1.2.1] - 2026-02-15

### Fixed

- **CRITICAL**: Added thread locks to prevent race conditions in client/request handling
    - Added `_clients_lock` for thread-safe client list operations
    - Added `_pending_requests_lock` for thread-safe request tracking
    - Added `_threads_lock` for thread management
    - All shared data structures are now properly protected

### Added

- `Events.ON_DISCONNECT` callback support
    - Called automatically when a client disconnects
    - Allows cleanup logic on client disconnect
- `Request.respond(response)` helper method
    - Simplifies request-response correlation
    - No need to manually pass `request_id=...`

### Changed

- `ClientInfo` now includes `thread_id` for better thread management

## [1.2.0] - 2026-02-11

### Added

- **Integrated Logger System**: Production-ready logging with powerful features
    - `Logger.get_instance()` - Singleton logger accessible throughout the application
    - Colorful console output with ANSI colors for better readability
    - File logging with automatic rotation based on file size
    - Multiple log levels: TRACE, DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL
    - Configurable via `LoggerConfig` with extensive options
    - Automatic caller information (file:line) tracking
    - Thread-safe implementation for multi-threaded applications
    - Optional async file writing for high-performance scenarios
    - Zero configuration required - works great with defaults
- **Comprehensive Logging**: Added detailed logging throughout the entire codebase
    - Client operations (connect, disconnect, send, receive)
    - Server operations (start, stop, client handling)
    - Network operations (data transmission, parsing)
    - Error conditions with detailed context
    - Request/response tracking with request IDs
- **Enhanced Sender**: Improved broadcasting capabilities
    - `except_clients` parameter to exclude specific clients from broadcasts
    - Better error reporting and statistics
    - Detailed logging of broadcast operations
    - Success rate tracking for broadcast operations
- **Foundation for v1.3.0**: Prepared infrastructure for handshake system
    - HELLO message type added to system types
    - Architecture ready for connection handshake protocol
    - Base structure for client authentication

### Changed

- **API Improvements**: More intuitive method names
    - `bind()` → `set_callback()` for event binding
    - `Bindings` enum → `Events` enum for consistency
    - More descriptive variable names throughout
- **Security Enhancements**:
    - Improved error handling in network operations
    - Better data validation in request parsing
    - Enhanced exception handling with detailed error messages
    - More robust connection state management
- **Code Quality**:
    - Refactored multiple code sections for better maintainability
    - Improved type hints and documentation
    - Better separation of concerns
    - More consistent error handling patterns

### Fixed

- Minor bugs in connection handling
- Edge cases in broadcast operations
- Race conditions in multi-threaded scenarios
- Memory leaks in logger file rotation
- Improved socket cleanup on disconnection

### Technical

- Logger singleton pattern implementation
- File rotation with configurable backup count
- Async buffer flushing for file writes
- Enhanced exception hierarchy
- Better thread management in server
- Improved socket timeout handling

### Breaking Changes

- `bind()` method renamed to `set_callback()`
- `Bindings` enum renamed to `Events`

### Migration Guide

```python
# Before (v1.1.x)
from veltix import Bindings

server.bind(Bindings.ON_RECV, callback)
client.bind(Bindings.ON_RECV, callback)

# After (v1.2.0)
from veltix import Events

server.set_callback(Events.ON_RECV, callback)
client.set_callback(Events.ON_RECV, callback)
```

## [1.1.0] - 2026-02-08

### Added

- **Request/Response pattern**: New `send_and_wait()` method for synchronous request-response communication
    - Client-side: `client.send_and_wait(request, timeout=5.0)`
    - Server-side: `server.send_and_wait(request, client, timeout=5.0)`
    - Automatic response matching via UUID-based request tracking
    - Built-in timeout support to prevent infinite waiting
- **Built-in Ping/Pong functionality**:
    - `client.ping_server(timeout=2.0)` - Measure server latency from client
    - `server.ping_client(client, timeout=2.0)` - Measure client latency from server
    - Automatic PING/PONG message handling (no manual implementation needed)
    - Returns latency in milliseconds
- **Latency measurement**: `Response.latency` property calculates round-trip time automatically
- **UUID request tracking**: All requests now have a unique `request_id` for matching responses

### Fixed

- UUID formatting in request/response parsing (now properly maintains UUID format with hyphens)
- Request ID preservation in PING/PONG responses

### Technical

- Added `_pending_requests` queue system for managing async responses
- Improved message routing logic to handle both callbacks and waiting requests
- Enhanced protocol to include 16-byte UUID field in message header

## [1.0.0] - 2026-02-06

### Added

- TCP Server with multi-threading support
- TCP Client with event-driven callbacks
- Binary protocol with SHA256 integrity verification
- Custom MessageType system with code ranges:
    - 0-199: System messages
    - 200-499: User messages
    - 500+: Plugin messages
- Event binding system (ON_RECV, ON_CONNECT)
- Zero dependencies - pure Python stdlib only
- Message broadcasting to multiple clients
- Automatic message integrity checks
- Thread-safe client handling

### Features

- Message integrity verification using SHA256 hashing
- Extensible message types via MessageTypeRegistry
- Event-driven callbacks for clean code organization
- Multi-threaded server handling multiple connections
- Simple and intuitive API design

### Initial Release

- Core networking functionality
- Complete documentation
- Example implementations (echo server, chat server)
- MIT License
