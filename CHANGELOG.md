# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0b3] - 2026-07-23

### Breaking Changes

- **`ERROR` and `INVALID_REQUEST` system types removed**: `MessageType(20, "error")` and
  `MessageType(21, "invalid_request")` are no longer exported from the public API or defined
  in `system_types.py`. Only `PING` and `PONG` remain as system types
  ([d861a8d](https://github.com/NytroxDev/Veltix/commit/d861a8d)).
- **`SocketEvents` enum removed**: unused `SocketEvents` enum deleted from `base_socket.py`
  ([5d115d4](https://github.com/NytroxDev/Veltix/commit/5d115d4)).

### Added

- **`InvalidContentError` exported**: now available via `from veltix import InvalidContentError`
  ([32257f4](https://github.com/NytroxDev/Veltix/commit/32257f4)).
- **Google-style docstrings**: comprehensive docstrings added across all major modules:
  `ClientInfo` ([b160e13](https://github.com/NytroxDev/Veltix/commit/b160e13)),
  `BaseSocket` / `ClientsManager` ([154c9ea](https://github.com/NytroxDev/Veltix/commit/154c9ea)),
  `MessageBuffer` ([628970e](https://github.com/NytroxDev/Veltix/commit/628970e)),
  `Logger` ([3df32f5](https://github.com/NytroxDev/Veltix/commit/3df32f5)),
  `VeltixBus` / event enums ([c8bce9f](https://github.com/NytroxDev/Veltix/commit/c8bce9f)),
  `HandshakeHandler` / `RulesManager` / rules ([94b57b2](https://github.com/NytroxDev/Veltix/commit/94b57b2)),
  `ReconnectHandler` ([b07c584](https://github.com/NytroxDev/Veltix/commit/b07c584)).

### Changed

- **Project migrated to `src` layout + Hatch build system**: package source moved from
  `veltix/` to `src/veltix/`, build backend replaced from `setuptools` with `hatchling`,
  `version.py` moved to `internal/version.py`. Added `publish.yml` workflow for automated
  PyPI releases ([28120ef](https://github.com/NytroxDev/Veltix/commit/28120ef)).
- **License migrated to SPDX**: deprecated classifier removed, SPDX string used in
  `pyproject.toml` ([440f9b6](https://github.com/NytroxDev/Veltix/commit/440f9b6)).
- **`from __future__ import annotations`** added across modules for forward reference
  compatibility ([ab2b68d](https://github.com/NytroxDev/Veltix/commit/ab2b68d)).
- **`Sender` type annotations**: bare `list`/`set` annotations replaced with typed
  `_ClientLike` alias ([c960b6e](https://github.com/NytroxDev/Veltix/commit/c960b6e)).
- **`ReconnectHandler` constructor**: `bus` parameter typed as `Optional`
  ([f2c30f3](https://github.com/NytroxDev/Veltix/commit/f2c30f3)).
- **`Request` annotations**: explicit type annotations added for `flags` and `type`
  ([a031371](https://github.com/NytroxDev/Veltix/commit/a031371)).
- **`pyproject.toml`**: pytest version constraint lowered to `>=8.0`
  ([d4cdb33](https://github.com/NytroxDev/Veltix/commit/d4cdb33)).
- **`Sender` uses `Sequence`** instead of `list` for `broadcast()` and `get_all_clients`,
  accepting any iterable ([7198372](https://github.com/NytroxDev/Veltix/commit/7198372)).

### Fixed

- **Thread safety: `Server._started` / `_closed`** protected with lock to prevent
  TOCTOU race conditions ([3d0b49a](https://github.com/NytroxDev/Veltix/commit/3d0b49a)).
- **Thread safety: `Server.running`** replaced bare `bool` with `threading.Event` for
  cross-thread safety ([b4889bd](https://github.com/NytroxDev/Veltix/commit/b4889bd)).
- **Thread safety: `Client.is_connected` / `running`** protected with lock to prevent
  cross-thread races ([d3351e8](https://github.com/NytroxDev/Veltix/commit/d3351e8)).
- **Thread safety: `Client._fail_count` / `_stop_retry_flag`** protected with lock to
  prevent cross-thread races ([248c5be](https://github.com/NytroxDev/Veltix/commit/248c5be)).
- **Thread safety: `handshake_done` race** now set only after handshake succeeds to prevent
  race with readers ([cf99ff5](https://github.com/NytroxDev/Veltix/commit/cf99ff5)).
- **Thread safety: Logger lock** use context manager for lock in `__init__` to prevent
  deadlock on exception ([76fc827](https://github.com/NytroxDev/Veltix/commit/76fc827)).
- **`PingRule` crash**: replaced `assert` with explicit `SenderError` checks
  ([863f3b3](https://github.com/NytroxDev/Veltix/commit/863f3b3)).
- **`handle()` return type**: handler returns `bool` instead of `Exception`, simplifying
  callers ([653c44e](https://github.com/NytroxDev/Veltix/commit/653c44e)).
- **Duplicate `SOCKET_DISCONNECTED` subscription**: client no longer subscribes twice to the
  disconnect event ([05d6fa0](https://github.com/NytroxDev/Veltix/commit/05d6fa0)).
- **Import paths after `src` layout migration**: corrected in `reconnect_handler.py`
  ([e02ef59](https://github.com/NytroxDev/Veltix/commit/e02ef59)), `request_handler.py`
  ([74d06cf](https://github.com/NytroxDev/Veltix/commit/74d06cf)).
- **`Response._text_cached` type ignore**: removed unnecessary `type: ignore` comment
  ([3df28b2](https://github.com/NytroxDev/Veltix/commit/3df28b2)).
- **Sender broadcast error logging**: improved error logging in broadcast exception handling
  ([40197ab](https://github.com/NytroxDev/Veltix/commit/40197ab)).
- **`Response.text`** now wraps cached value in `str()` to ensure consistent return type
  ([12b0e35](https://github.com/NytroxDev/Veltix/commit/12b0e35)).
- **`Sender.broadcast`** logic restructured to avoid unnecessary callback when client list is
  provided directly ([daae348](https://github.com/NytroxDev/Veltix/commit/daae348)).
- **Parser error messages**: standardized punctuation across error messages
  ([e39d97f](https://github.com/NytroxDev/Veltix/commit/e39d97f)).

### Refactored

- **`Sender` docstrings**: redundant docstrings removed
  ([cafbe61](https://github.com/NytroxDev/Veltix/commit/cafbe61)).
- **`ClientsManager.__init__`**: explicit return type added
  ([f995606](https://github.com/NytroxDev/Veltix/commit/f995606)).
- **`@dataclass` decorator**: unnecessary parentheses removed in `compatibility.py`
  ([d6248be](https://github.com/NytroxDev/Veltix/commit/d6248be)).

### Chore / CI

- **GitHub Actions upgraded to v6** (Node 24)
  ([959edce](https://github.com/NytroxDev/Veltix/commit/959edce)).
- **CI install step**: package now installed before running tests
  ([aafbb35](https://github.com/NytroxDev/Veltix/commit/aafbb35)).
- **`mypy` comment**: added explanation for `python_version = 3.10` in `pyproject.toml`
  ([7120d88](https://github.com/NytroxDev/Veltix/commit/7120d88)).
- **Discord invite links** updated across documentation
  ([8645438](https://github.com/NytroxDev/Veltix/commit/8645438)).
- **Unused imports** cleaned up in `sender.py`
  ([c54c0e6](https://github.com/NytroxDev/Veltix/commit/c54c0e6)).
- **mypy tests override removed**: `disallow_untyped_defs` now enforced on test files
  ([57fb4e7](https://github.com/NytroxDev/Veltix/commit/57fb4e7)).
- **Type ignore comments removed**: unnecessary `# type: ignore[assignment]` in `ReconnectHandler`
  ([0d95efc](https://github.com/NytroxDev/Veltix/commit/0d95efc)).
- **Formatting fixes**: docstring typo in `Server.send()`, collapsed multi-line signatures in
  `RequestHandler` and `BaseSocket`, line wrap in `AsyncSocket`
  ([37bb385](https://github.com/NytroxDev/Veltix/commit/37bb385)).

### Tests

- **564 tests**: `SocketEvents` tests removed, import paths updated for `src` layout
  ([6998c6e](https://github.com/NytroxDev/Veltix/commit/6998c6e)),
  handshake test import reordered ([f096f39](https://github.com/NytroxDev/Veltix/commit/f096f39)).

---

## [2.0.0b2] - 2026-07-16

### Added

- **`Response.text`** : lazy, cached UTF-8 decoding property. Replaces manual `response.content.decode()`
  ([8fc9085](https://github.com/NytroxDev/Veltix/commit/8fc9085)).
- **`Response.json`** : lazy, cached JSON decoding property. Raises `InvalidContentError` on invalid JSON
  ([8fc9085](https://github.com/NytroxDev/Veltix/commit/8fc9085)).
- **`Response.is_text` / `Response.is_json`** : safe boolean checks without raising exceptions
  ([8fc9085](https://github.com/NytroxDev/Veltix/commit/8fc9085)).
- **`Request` text/json payloads** : `Request(MY_TYPE, text="hello")` and `Request(MY_TYPE, json={"k": "v"})`
  auto-encode, exactly one payload arg required ([7cfe9d3](https://github.com/NytroxDev/Veltix/commit/7cfe9d3)).
- **`Request.respond(response)`** : copies `request_id` from a received response for request/response correlation
  ([7cfe9d3](https://github.com/NytroxDev/Veltix/commit/7cfe9d3)).
- **`Server.send()` / `Server.broadcast()`** : convenience methods that accept `ClientInfo` or `BaseSocket` directly,
  no need to access `server.sender` ([5b0b10e](https://github.com/NytroxDev/Veltix/commit/5b0b10e)).
- **`Client.send()`** : convenience method, same pattern as `Server.send()`
  ([5b0b10e](https://github.com/NytroxDev/Veltix/commit/5b0b10e)).
- **`server.wait_until_closed()` / `client.wait_until_closed()`** : block until shutdown
  ([20331c4](https://github.com/NytroxDev/Veltix/commit/20331c4)).
- **`server.restart()`** : stop + start, preserves routes and callbacks
  ([5b0b10e](https://github.com/NytroxDev/Veltix/commit/5b0b10e)).
- **`MessageParser`** : extracted from `RequestHandler`, standalone message parsing module
  ([908106a](https://github.com/NytroxDev/Veltix/commit/908106a)).

### Changed

- **`Response` extracted to own module** : `Response` class moved from `network/request.py` to `network/response.py`
  ([5b0b10e](https://github.com/NytroxDev/Veltix/commit/5b0b10e)).

### Fixed

- **`send_and_wait()` always timed out for non-first clients** : `_resolve_global_id()` was adding `id_offset` to
  `wire_id`, but `pending_requests` is keyed by raw `wire_id` from `IDAllocator`, so the lookup always missed
  ([2438be4](https://github.com/NytroxDev/Veltix/commit/2438be4)).
- **Keyboard interrupt handling during client shutdown** : `wait_until_closed()` now catches `KeyboardInterrupt`
  gracefully ([20331c4](https://github.com/NytroxDev/Veltix/commit/20331c4)).
- **Incorrect import paths** after `Response` extraction : `rules.py` and `message_buffer.py` referenced old location
  ([efc3c5c](https://github.com/NytroxDev/Veltix/commit/efc3c5c),
  [e54f98c](https://github.com/NytroxDev/Veltix/commit/e54f98c)).
- **`InvalidContentError` import path** : fixed incorrect import after module reorganization
  ([499aa4a](https://github.com/NytroxDev/Veltix/commit/499aa4a)).
- **Version string** : `Version.from_str()` now handles pre-release suffixes like `b1`, `b2` correctly
  ([4502806](https://github.com/NytroxDev/Veltix/commit/4502806)).

### Tests

- **571 tests** : new tests for `Response` content decoding, `Request` payload initialization and validation,
  `IDAllocator`, `ClientAllocator`, and `_resolve_global_id` fix verification
  ([250bcb8](https://github.com/NytroxDev/Veltix/commit/250bcb8),
  [961c4df](https://github.com/NytroxDev/Veltix/commit/961c4df)).

---

## [2.0.0b1] - 2026-07-13

> **Migration guide:** [docs/guides/migration.md](docs/guides/migration.md#v190--v200)

### Added

- **Flags field in protocol header** (1 byte) — new `MessageFlag(IntFlag)` in `network/flags.py` for future
  compression/encryption support. Currently only
  `NONE = 0x00` ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).
- **`IDAllocator`** — thread-safe monotonic counter for per-connection request IDs, replaces `generate_random_id()`.
  Allocates sequential IDs within a fixed range `[0, max_ids)`, wraps around after reaching the limit
  ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).
- **`ClientAllocator`** — server-side counter that assigns unique offsets to connected clients so that
  `wire_id + client_offset` produces globally unique IDs across all clients
  ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).
- **`ServerConfig.id_window`** — configurable unique ID window per direction (default: 30000). Sent to clients
  during the handshake via `meta.id_window` ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).
- **Handshake meta** — server now sends `{"v": "2.0.0", "meta": {"id_window": 30000}}` to clients
  ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).

### Changed

#### Wire protocol (Breaking)

- **Header size reduced from 16 to 15 bytes** — new layout:
  `[2B MAGIC][1B flags][2B code][4B size][4B CRC][2B request_id][content]`
  ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).
- **`request_id` type changed from `bytes` (4 bytes) to `int` (2 bytes)** — uint16, max 65535. The
  `generate_random_id()`
  function has been removed; IDs are now auto-allocated by `IDAllocator` via the `Sender`
  ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).
- **`Response.request_id`** is now a public `int` property (was `bytes`). Internal storage is `_request_id`.
  ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).
- **`Response._hash`** field is now private (prefixed with `_`). No longer accessible as `response.hash`.
  ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).
- **`REQUEST_ID_SIZE`** changed from `4` to `2` ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).
- **`HEADER_SIZE`** changed from `16` to `15` ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).
- **Split ID ranges** — Server→Client uses `[0, id_window)`, Client→Server uses `[id_window, id_window*2)`.
  Each client receives a unique offset via
  `ClientAllocator` ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).
- **`Sender` auto-allocates request IDs** — `send()` now allocates via `IDAllocator` if `request_id is None`
  ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).
- **`MessageBuffer` struct updated** — new struct `">2sBHI4s2s"` for the 15-byte header format
  ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).

### Removed

- **`generate_random_id()`** — replaced by
  `IDAllocator` ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).

### Tests

- **522 tests** — all existing tests updated for the new wire format; new tests added for `IDAllocator`,
  `ClientAllocator`, `MessageFlag`, split ranges, and handshake `id_window` exchange
  ([49fb15a](https://github.com/NytroxDev/Veltix/commit/49fb15a)).

---

## [1.9.0] - 2026-07-10

### Added

- **VeltixBus event system** : new `VeltixBus` (powered by vendored Avyra `EventBus`) replaces the Logger singleton
  across all core modules. Emits structured `ServerEvent`, `ClientEvent`, `MessageEvent`, `ProtocolEvent`,
  `ErrorEvent`, `ReconnectEvent`, and `LogEvent` for full observability via a single subscription
  ([a1c70e2](https://github.com/NytroxDev/Veltix/commit/a1c70e2),
  [fe9e5bb](https://github.com/NytroxDev/Veltix/commit/fe9e5bb),
  [3aebb27](https://github.com/NytroxDev/Veltix/commit/3aebb27)).
- **Benchmark now optional** : `psutil` is no longer a hard dependency. Install with `pip install veltix[benchmark]`
  to use the benchmark suite
  ([0437d05](https://github.com/NytroxDev/Veltix/commit/0437d05)).

### Changed

- **Internal architecture** : Logger singleton replaced with per-instance `VeltixBus` injected into `Server`,
  `Client`, `BaseSocket`, `RequestHandler`, `Sender`, `ReconnectHandler`, `ClientsManager`, and `MessageBuffer`
  ([80bded4](https://github.com/NytroxDev/Veltix/commit/80bded4),
  [14fb528](https://github.com/NytroxDev/Veltix/commit/14fb528),
  [9ac46b8](https://github.com/NytroxDev/Veltix/commit/9ac46b8),
  [2cf3390](https://github.com/NytroxDev/Veltix/commit/2cf3390),
  [36ddf0d](https://github.com/NytroxDev/Veltix/commit/36ddf0d),
  [73fae89](https://github.com/NytroxDev/Veltix/commit/73fae89),
  [efe2a58](https://github.com/NytroxDev/Veltix/commit/efe2a58),
  [4b09253](https://github.com/NytroxDev/Veltix/commit/4b09253)).
- **Vendored Avyra v1.0.0** : event-bus library copied into `veltix/_vendor/avyra/` with Python 3.8 compat
  ([a1c70e2](https://github.com/NytroxDev/Veltix/commit/a1c70e2)).
- **Backward compatible** : public API is unchanged; the old `Events` enum is kept for compatibility.

### Fixed

- **Race condition in handshake** : `handshake_done = True` now set before `do_server_handshake()` to close a race
  condition ([6e9069f](https://github.com/NytroxDev/Veltix/commit/6e9069f)).
- **Dead Logger singleton removed from `request.py`** : the last Logger references in the request module were cleaned up
  ([4a19b32](https://github.com/NytroxDev/Veltix/commit/4a19b32)).

### Tests

- **Avyra vendor tests added** : 70 tests for the vendored event-bus library, plus a version test; total suite reaches
  497 tests ([077ff45](https://github.com/NytroxDev/Veltix/commit/077ff45),
  [2f75f16](https://github.com/NytroxDev/Veltix/commit/2f75f16)).

## [1.8.1] - 2026-07-07

### Fixed

- **`SO_REUSEADDR` moved to `bind()` only** : the socket option was being set on both server and client sockets; now
  restricted to the listening socket only ([b117547](https://github.com/NytroxDev/Veltix/commit/b117547)).
- **`handshake_timeout` propagated to client socket instances** : `ClientConfig.handshake_timeout` was not forwarded to
  the underlying socket; the default timeout was always used instead of the configured
  value ([4e5a7db](https://github.com/NytroxDev/Veltix/commit/4e5a7db)).
- **AsyncSocket selector loop busy-loop after self-disconnect** : when the server closed a client connection, the
  selector could enter a busy-loop reading from a closed fd. Now breaks out immediately on
  self-disconnect ([7543f1d](https://github.com/NytroxDev/Veltix/commit/7543f1d)).
- **Handshake encode/decode exceptions no longer swallowed** : `_encode()` and `_decode()` were silently catching all
  JSON errors; exceptions now propagate properly. Also fixes a Python 3.8 compatibility regression in
  `request_handler.py` ([feb8736](https://github.com/NytroxDev/Veltix/commit/feb8736), [6d76612](https://github.com/NytroxDev/Veltix/commit/6d76612)).
- **Client config no longer mutated during retry** : `client.retry(max=N)` was overwriting the original
  `ClientConfig.retry`; now uses an internal override ([91c872d](https://github.com/NytroxDev/Veltix/commit/91c872d)).
- **Logger Writer type annotations** : `_file_path` normalized to `Optional[Path]`, `_initialized` guard uses
  class-level `RLock`, `__post_init__` missing return type
  added ([ea823fe](https://github.com/NytroxDev/Veltix/commit/ea823fe), [3bfa9ad](https://github.com/NytroxDev/Veltix/commit/3bfa9ad), [f7f24b9](https://github.com/NytroxDev/Veltix/commit/f7f24b9)).

### Changed

- **`Server.sender` / `Client.sender` now a property** : `get_sender()` is deprecated and will be removed in a future
  version. Use `server.sender` and `client.sender` directly instead. All examples, tests, and docs have been migrated
  ([66eb6cb](https://github.com/NytroxDev/Veltix/commit/66eb6cb), [5fbbf38](https://github.com/NytroxDev/Veltix/commit/5fbbf38)).
- **`BaseSocket` refactored from `Protocol` to `ABC`** : stronger inheritance guarantees and slot-sharing in subclasses.
  No user-facing changes required ([4b577b5](https://github.com/NytroxDev/Veltix/commit/4b577b5)).
- **`PendingRequestRule.can_handle` now truthful** : previously returned `False` requiring explicit `try_handle()`
  dispatch; now acts as a standard rule ([11c3cbb](https://github.com/NytroxDev/Veltix/commit/11c3cbb)).

### Performance

- **Test suite ~7× faster** : runtime reduced from ~49s to ~7s via `pytest-xdist`, reduced cleanup `sleep()`, and lower
  `handshake_timeout` in tests ([fd26e72](https://github.com/NytroxDev/Veltix/commit/fd26e72)).

### Tests

- **30 new unit tests** for `ThreadingSocket` and `AsyncSocket` error paths (send failures, accept failures, handshake
  failures) ([42b1ba5](https://github.com/NytroxDev/Veltix/commit/42b1ba5)).
- **100% coverage on `Writer`** : comprehensive tests covering file rotation, buffer flushing, edge
  cases ([7195060](https://github.com/NytroxDev/Veltix/commit/7195060)).

### Chore

- **CI lint and typecheck jobs added** : `ruff check` and `mypy veltix/` now run in
  CI ([e2fa945](https://github.com/NytroxDev/Veltix/commit/e2fa945)).
- **Release script** (`scripts/release.sh`) : ruff, mypy, version consistency, compatibility table, tests, build
  check ([9cd5545](https://github.com/NytroxDev/Veltix/commit/9cd5545), [7abc61f](https://github.com/NytroxDev/Veltix/commit/7abc61f)).
- **Ruff auto-fix pass** : entire codebase reformatted; all rules (B017, N806, B007, TC001, TC003, SIM110)
  resolved ([bb28218](https://github.com/NytroxDev/Veltix/commit/bb28218), [c42d90f](https://github.com/NytroxDev/Veltix/commit/c42d90f), [41e97e8](https://github.com/NytroxDev/Veltix/commit/41e97e8)).
- **43 commits** from v1.8.0 : full housekeeping cycle to tighten types, fix edge cases, and solidify CI.

---

## [1.8.0] - 2026-07-04

### Added

#### JSON Raw-Socket Handshake (Breaking)

HELLO/HELLO_ACK message-based handshake replaced with a **JSON raw-socket protocol**:

- Handshake now exchanges JSON payloads (`{"v": "1.8.0", "meta": {}}`) directly over the TCP
  stream, before any Veltix framing is used.
- **Synchronous**: `client.connect()` blocks until the JSON handshake completes or fails.
  No more `_handshake_done` Event or deferred handshake state.
- `HandshakeHandler` rewritten: `_encode()` / `_decode()` for JSON serialization,
  `_send_handshake()` / `_recv_handshake()` for raw socket I/O, `do_server_handshake()` /
  `do_client_handshake()` as the public entry points.
- Server-side handshake executes before the client is registered in `ClientsManager` on the
  `AsyncSocket` backend — the `ClientInfo` is created, registered, and only marked
  `handshake_done=True` after a successful handshake. On failure, cleanup is immediate and
  complete.

### Removed

- **`HELLO` / `HELLO_ACK` system types** (codes 10, 11) — no longer used.
- **`HelloRule`** — removed from `handler/rules.py` and `ALL_RULES`.
- **`_handshake_done` Event** from `Client` — handshake is now synchronous; `connect()`
  returns True/False directly.
- **`handshake_timeout` config** (retained in config for future use but no longer used in
  the handshake path — the raw socket timeout serves the same purpose).
- **`_handshake_pending` / `_process_pending_handshakes()`** dead code from `AsyncSocket`
  (noted as dead in v1.7.0 changelog).

### Changed

- **`ERROR` / `INVALID_REQUEST` system types** (codes 20, 21) confirmed as kept and
  re-exported.
- **`HandshakeHandler` constructor** no longer takes a `sender` parameter — only `mode`.
- **Wire protocol**: Handshake no longer uses MAGIC/HEADER_SIZE framing. Post-handshake
  messages continue to use the existing Veltix frame format unchanged.
- **Compatibility table**: only `Version(1, 8, 0) : [Version(1, 8, 0)]`.
- **Python 3.8 compatibility**: all `X | Y` union syntax replaced with `Union[X, Y]`
  across `benchmark/`, `logger/config.py`, `network/request.py`.

### Fixed

- **`AsyncSocket` server-side handshake ordering**: `ClientInfo` is now created and
  registered in `ClientsManager` *before* the handshake, not after. This ensures the
  server has a consistent view of all connecting clients regardless of handshake outcome.
- **`AsyncSocket._close_server_client()`** now calls `shutdown()` before `close()` to
  ensure clean TCP teardown. Added `_shutdown_socket()` helper.
- **`ThreadingSocket`** also uses `_shutdown_socket()` before `close()` on disconnect
  and shutdown.

### Tests

- **377 tests** (up from 261) — test count reflects the broader coverage built across
  the 1.7.x cycle.
- **`test_handshake.py`** rewritten: tests JSON encode/decode roundtrips, version check
  logic, integration with real sockets (success, version mismatch, timeout, multiple
  clients sequential).
- **`test_message_type.py`**: `test_hello_types_exist` replaced with `test_error_types_exist`.
- **`test_compatibility.py`**: version references updated to 1.8.0.
- **`test_client_server.py`**: two new tests verify handshake registration ordering and
  failed-handshake cleanup.

### Docs

- **AGENTS.md**: version 1.8.0, system types updated, HelloRule removed, examples updated.
- **README.md**: handshake description updated, test count corrected.
- **docs/**: index.md, migration.md updated for v1.8.0 changes.

---

## [1.7.5] - 2026-07-02

### Fixed

#### Socket Core

- **`SO_REUSEPORT` guarded on all platforms** — `socket.SO_REUSEPORT` doesn't exist on Windows and may raise
  `AttributeError` on older Python builds ; wrapped with `contextlib.suppress` in both `ThreadingSocket` and
  `AsyncSocket` ([330be08])

### Chore

- **Compatibility table updated** — `Version(1, 7, 5)` registered as compatible with 1.7.0–1.7.5

## [1.7.2] - 2026-06-20

### Added

- **108 new tests** — coverage increased across routing, handshake, reconnection, and logging ; existing tests
  accelerated ([be78e94])

### Fixed

#### Server

- **`ClientInfo.tags` locked** — tags dict now protected with `threading.Lock` across all reads/writes ; property
  returns a read-only copy ([84e586d], [1c2a60d])
- **`_routes` dict race condition** — all reads and writes now properly locked ([1148fe4])

#### Client

- **`_handshake_done` cleared before reconnect** — prevents stale event state from blocking the next connection
  attempt ([7e89e74])
- **Premature disconnect callback on connect** — guarded the window between socket bind and handshake completion
  ([380b1ed])
- **Old socket not closed on reconnect** — `close()` and `shutdown()` now called on the previous socket and handler
  before creating new ones ([5063baa])
- **Double reconnect loop** — `_reconnect_lock` prevents concurrent reconnection attempts ([1a8d78c])
- **Imports cleaned up** — unused imports removed from `client.py` ([c6cbc23])

#### Logger / Writer

- **`_flush_buffer` lock** — file writer flush access wrapped in thread-safe lock ([3677d1c])

#### ReconnectHandler

- **Log message language corrected** — French alert message fixed to proper English ([b33b39b])

### CI

- **`actions/checkout` and `setup-python` versions updated** — workflow now uses latest GitHub Actions versions
  ([0592e36])

### Docs

- **Guides and quickstart refined** — `retry` parameter documentation adjusted, info sections updated ([a405433])

### Chore

- **Discord invite link updated** in `pyproject.toml` ([f381a2c])

---

## [1.7.1] - 2026-06-14

### Fixed

#### AsyncSocket

- **`_close_server_client()` idempotent on selector unregister** — calling `unregister()` on an already-closed file
  descriptor no longer raises `KeyError` ([1bee90e])
- **Selector threads set as daemons** — ensures the process can exit cleanly even if selector threads are still running
  during shutdown ([d2ffed4])

#### Server

- **`ClientInfo._id` with `__eq__`/`__hash__`** — stable identity for `ClientInfo` objects, fixing set/dict membership
  issues ([48cbbf2])
- **`close_client()` type hint** — `id_` parameter type fixed to `Optional[int]` ([dd991e5])
- **Handshake version validation** — HELLO_ACK version is now validated in `_check_server_handshake`, rejecting
  incompatible clients earlier ([6d377ee])

#### Client / Sender

- **`_sock.close()` wrapped in try/except** — client cleanup is never skipped even if the socket is already
  closed ([24fc1e5])
- **`request_id` bytes in log f-strings** — `.hex()` prevents `TypeError` from raw bytes interpolation in log
  messages ([91f68e8])

#### Python < 3.11 Compatibility

- **`TimeoutError` replaced with `socket.timeout`** — `TimeoutError` is a builtin only since Python 3.11; now uses
  `socket.timeout` which exists in all supported versions ([2069879])

#### RequestHandler

- **`sender` parameter made `Optional`** — constructor accepts `None` sender, matching usage from client-side
  paths ([2d20a88])
- **Dead `handle()` replaced with no-op** — `PendingRequestRule.handle()` was unreachable (only `try_handle()` is used);
  no longer misleading ([56df37a])

### Features

- **Export `NetworkError` and `TimeoutError` in `__all__`** — both exception classes are now part of the public
  API ([4a6e7a6])

### Chores

- **Remove unused `HEARTBEAT` message type** — was never registered or referenced in the codebase ([cf76069])

### Documentation

- **AGENTS.md** — new comprehensive guide for AI agents with project conventions, API reference, and
  examples ([c9c3683])
- **AGENTS.md expanded** — added performance benchmarks, detailed examples, and updated conventions ([12aff33])
- **AGENTS.md SocketCore default** — updated to reflect `SocketCore.ASYNC` as the default backend ([b3388d4])
- **AGENTS.md backward compatibility** — fixed constraint description to match actual policy ([a5bf915])
- **Sender docstrings** — translated from French to English ([8f4a26c])
- **README rewrite** — added socket comparison table, backend selection guide, and maturity highlights ([5f843e0])
- **README badge** — added AI guide badge linking to AGENTS.md ([8aa5b94])

### Refactors

- **Sender instances reused** — client and server examples reuse `sender` for broadcasts and sends, improving
  readability ([8807f39], [55f7160])
- **Broadcast excluded sender** — `CHAT` handler excludes the sender client from broadcast recipients ([b83c181])
- **`add_tag()` used in CHANNEL_JOIN handler** — replaces direct `tags` dict update with the idiomatic
  method ([a9b21cc])

### Tests

- **Handshake version rejection** — new test verifying the server rejects an incompatible HELLO_ACK version ([b7a1d84])

---

## [1.7.0] - 2026-06-09

### Added

#### AsyncSocket (Selectors-Based Backend)

New `SocketCore.ASYNC` backend (`veltix/socket_core/async_socket.py`) — a selectors-based
I/O loop that replaces the one-thread-per-client model:

- **Selector loop** with `selectors.DefaultSelector()` — single thread handles all clients,
  no thread-per-client overhead
- **`_accept_client()`** + **`_send_hello()`** — HELLO is sent immediately on accept,
  eliminating the 500 ms `select()` latency of the old deferred handshake queue
- **Client mode** — `connect()` / `disconnect()` / self-read via `_handle_self_read()`
- **`_close_server_client()`** — clean teardown with `close()` + `on_disconnect` callback
- **`_check_handshake_timeouts()`** — configurable timeout for stalled handshakes
- **`_create_client_instance()`** — factory method for per-client socket instances with
  their own selector, buffer, and handshake state

#### Protocol Hardening

- **MAGIC bytes** (`b"VX"`) prepended to every frame — validates frame alignment on
  the receiving end. Invalid magic triggers automatic stream resynchronization.
- **`MessageBuffer._resync()`** — on parse failure (CRC, size, or magic mismatch),
  searches the buffer for the next valid MAGIC byte and discards corrupted data.
  If no MAGIC is found, the entire buffer is cleared.
- **`MAX_BUFFER_SIZE`** — hard 20 MB limit on the accumulation buffer. Exceeding it
  clears the buffer entirely (DoS protection).
- **Per-message `max_message_size`** — individual message size validated at `parse()`
  time (default 10 MB).

#### Benchmark Suite Enhancements

- **`--socket-core` argument** — benchmark threading, async, or both backends
  side-by-side
- **`--runs N`** — run each benchmark N times and average all results, eliminating
  run-to-run noise
- **`--latency-iterations`** default increased from 2 000 to **50 000** for stable
  P95/P99/max stats
- **`average()` static methods** on all result models (`LatencyStats`, `MemoryResult`,
  `FpsResult`, `BurstResult`, `StressResult`) — `LatencyStats` concatenates raw
  samples for accurate percentile computation across runs
- **Side-by-side summary** — `--socket-core both` now displays threading and async
  results in adjacent columns for direct comparison
- **Benchmark label fix** — each per-bench output shows which backend is being tested
- **Callback executor error suppression** — `CallbackExecutor` errors no longer pollute
  benchmark output during teardown

#### Integration Tests

- **Parametrized over both backends** — all integration tests (`test_client_server.py`,
  `test_callback_executor.py`) run on both `SocketCore.THREADING` and `SocketCore.ASYNC`

### Changed

#### Protocol Wire Format (Breaking)

- **Header size increased from 14 to 16 bytes** — 2 bytes added for MAGIC (`b"VX"`)
  at the start of every frame
- **`Request.compile()`** now prepends MAGIC before the binary header
- **`Request.parse()`** validates MAGIC bytes first, then proceeds to type, CRC, and
  content. Raises `RequestError("Invalid magic bytes")` on mismatch.
- **`HEADER_SIZE` constant** updated from `14` to `16`
- **`_HEADER_STRUCT`** format changed from `">HI4s4s"` to `">2sHI4s4s"`
- **Version compatibility** — v1.7.0 is only compatible with itself. Entry added to
  `COMPATIBILITY` table: `Version(1, 7, 0): [Version(1, 7, 0)]`

#### MessageBuffer

- **`extract_messages()`** — uses `struct.unpack_from` to read MAGIC + content size
  in a single zero-copy operation (replaces `buffer[:2]` + `int.from_bytes(buffer[4:8])`)
- **`extract_messages()`** — passes `bytearray` slice directly to `Request.parse()`,
  eliminating an extra `bytes()` copy
- **`Request.parse()`** — accepts `bytes | bytearray` (type hint updated)

#### Sender

- **`broadcast()`** — compiles the `Request` once and reuses the serialized bytes
  for all recipients, instead of calling `data.compile()` per client

#### Test Protocol

- **`test_invalid_magic_bytes`** — new test verifying that corrupted magic is properly
  rejected
- **`test_message_buffer.py`** — 15 new tests covering corruption recovery,
  resynchronization (multiple corruptions, continuous garbage), and buffer
  protection (overflow, max-size enforcement)
- **All existing parse tests updated** for 16-byte header and MAGIC offsets

### Fixed

#### AsyncSocket

- **Race condition on HELLO delivery** — the original code queued HELLO sending to
  `_process_pending_handshakes()` which ran after `select()`, adding up to 500 ms
  latency before the handshake initiated. Fixed by sending HELLO immediately in
  `_accept_client()` via the new `_send_hello()` method.
- **`BlockingIOError` on send** — caught and retried with temporary blocking mode
- **`accept()` errors** — `BlockingIOError` and `OSError` caught gracefully
- **Non-blocking mode** — all client sockets set to non-blocking on creation
- **Handshake timeout** — stalled connections are cleaned up after `handshake_timeout`
  seconds
- **`on_disconnect` in self-read** — client-side disconnection properly triggers
  the callback

#### ThreadingSocket

- **`max_client=-1` blocking accept** — when `max_client` was -1 (unlimited), the
  accept loop could block indefinitely. Now treated as "no limit".
- **`send()` `BlockingIOError` fallback** — caught and retried with blocking mode
- **`on_disconnect` in self-read** — server-originated disconnection now fires the
  callback

### Internal

- **`_handshake_pending` / `_process_pending_handshakes()`** — now dead code in
  `AsyncSocket` (nothing pushes to the pending queue since `_send_hello` is called
  directly). Left in place for backward compatibility; will be removed in v1.8.0.
- **`_check_handshake_timeouts()`** — shared between threading and async backends
- **Message buffer pre-compiled struct** — `_MAGIC_AND_SIZE = Struct(">2s2xI")`
  for zero-copy magic + size extraction

### Performance (v1.7.0 @ 5-run average)

#### Memory

| Metric           | threading | async    |
|------------------|-----------|----------|
| Idle server      | 45.6 KB   | 4 KB     |
| Per client (avg) | 36.1 KB   | 12.4 KB  |
| Per client (min) | 17.6 KB   | 4 KB     |
| Per client (max) | 45.6 KB   | 16 KB    |
| Leak delta       | 423 KB    | 21 KB    |
| 50 clients       | 24.39 MB  | 23.63 MB |

#### Latency (250 000 pings)

| Metric     | threading | async    |
|------------|-----------|----------|
| Avg        | 0.032 ms  | 0.035 ms |
| P50        | 0.030 ms  | 0.035 ms |
| P95        | 0.042 ms  | 0.048 ms |
| P99        | 0.070 ms  | 0.079 ms |
| Throughput | 29 461/s  | 26 625/s |

#### Burst (10 000 × 64 B)

| Metric   | threading    | async        |
|----------|--------------|--------------|
| Send     | 52 109 msg/s | 52 296 msg/s |
| Recv     | 41 327 msg/s | 41 343 msg/s |
| Duration | 242.0 ms     | 244.1 ms     |

#### Stress (100 clients × 100 msg)

| Metric     | threading    | async        |
|------------|--------------|--------------|
| Throughput | 37 676 msg/s | 76 929 msg/s |
| Duration   | 267.0 ms     | 136.0 ms     |

Full benchmark comparison with v1.6.10: [PERFORMANCE.md](PERFORMANCE.md)

---

## [1.6.10] - 2026-06-07

### PerformanceMode Removal

- **Removed `PerformanceMode` enum**: `PerformanceMode.LOW / BALANCED / HIGH / AUTO` and
  `PerformanceModeSettings` dataclass deleted entirely. The socket timeout is now hardcoded
  to **0.5 s** across all configurations, matching the old `BALANCED` preset.
    - `ServerConfig.performance_mode` and `ClientConfig.performance_mode` no longer exist
    - `ServerConfig.__slots__` cleaned up: `_perf` attribute removed
    - All remaining `self._perf.socket_timeout` references replaced with `0.5`
    - Docs and guides cleared of PerformanceMode mentions

### Changed

- **`@route` server callback order unified**: server route callbacks now receive
  `(client, response)` as positional arguments, matching the `on_recv` signature.
  Previously they received `(response, client)`: update any custom route handlers.

- **Server callback type fixed**: `Server.clients` now returns `list[ClientInfo]`
  instead of `list[ClientEntry]`, preserving the documented public API. Internal
  `ClientEntry` objects are no longer exposed.

### Fixed

#### Protocol / MessageBuffer

- **Mutable `RecvResult` singletons replaced**: `RecvResult` instances were previously
  module-level singletons (`_OK`, `_TIMEOUT`, `_CLOSED`, `_ERROR`) shared across all
  calls. A mutating caller could corrupt the state of concurrent readers. Now returns
  a **new instance** on every `recv()` call.

- **MessageBuffer data loss after parse failure**: when `Request.parse()` raised an
  exception (corrupt message), `extract_messages()` silently discarded the message but
  kept the buffer untouched, causing an infinite loop of the same failing parse.
  Now **advances past the corrupt frame** (`buffer = buffer[total_size:]`) to resync
  the stream.

- **TOCTOU race in `PendingRequestRule`**: the rule checked `can_handle()` (lookup
  in `pending_requests`) but by the time `handle()` ran another thread had consumed
  the response, leaving the queue empty. Added `try_handle()` that atomically
  checks-and-puts, and `PendingRequestRule.can_handle()` returns `False`: the rule
  is now only invoked explicitly via `try_handle()`.

- **String `mode` not normalised to `Mode` enum**: `RequestHandler` and `Sender`
  accepted a raw `str` for `mode` but never converted it to `Mode`, causing `"client"`
  vs `Mode.CLIENT` mismatches. Both now call `Mode(mode)` on init.

#### Client / Reconnect

- **Disconnect / reconnect race**: when `disconnect()` was called while a retry
  thread was mid-`connect()`, two issues arose:
    1. Handshake timeout in the retry thread triggered a nested `disconnect()` call.
       Fixed by skipping `self.disconnect()` when `_from_retry=True`.
    2. `connect()` could return `True` after `stop_retry()` was set. Fixed by checking
       `_stop_retry_flag` after `context_connect()` returns, and closing the socket.
       Also added `context_get_socket()` to `ClientContext` protocol.

- **Client ignored `config.socket_core`**: `Client.connect()` always created a
  `ThreadingSocket` regardless of `ClientConfig.socket_core`. Now uses
  `self.config.socket_core.value()` like the server.

- **Retry loop started parallel threads**: calling `client.retry()` multiple times
  launched concurrent reconnect loops. Now guarded via `_retry_thread.is_alive()`.

- **`thread_handler` never joined in `close_all()`**: server's `close_all()` joined
  `start_th` but not `thread_handler`, leaving the receive thread alive until socket
  error. Now joins `thread_handler` with `None` guard and `current_thread` check.

- **Missing attrs in `_create_client_instance()`**: server-side client sockets created
  via `_create_client_instance()` were missing `start_th`, `threads`, `_threads_lock`,
  `n_th`, `_n_th_lock`, and `thread_handler`, causing `AttributeError` in `close_all()`.
  All attributes now properly initialized.

#### Server Lifecycle

- **Race on server start**: `listen()` was called inside the accept thread, creating
  a window where `bind()` returned before the socket was listening. Moved `listen()`
  before the accept thread starts.

- **Stale `running=True` on accept loop exit**: when `_accept_loop` exited on `OSError`,
  `self.running` stayed `True`. Now sets `self.running = False` on every exit path.

- **Thread pool not released**: `Server.close_all()` and `Client.disconnect()` neither
  called `request_handler.shutdown()` nor released the `ThreadPoolExecutor`. Now calls
  `shutdown(wait=False)` before closing the socket.

- **`TCP_NODELAY` not set on accepted sockets**: server-side client sockets accepted
  via `_accept_loop` did not have `TCP_NODELAY` enabled. Now applied in
  `_create_client_instance()`.

#### Handshake

- **Invalid HELLO connection leak**: when the client received an invalid HELLO,
  `HelloRule.handle()` logged a warning but did not close the connection. Now calls
  `sender.conn.close()` after logging.

- **Stray parenthesis in `HelloRule.close()`**: `HelloRule` was calling `close()` with
  a trailing `()` inside the method call, causing a `TypeError`. Fixed.

- **Missing bounds validation in `_decode_hello()`**: `_decode_hello()` read the
  version length prefix and used it to slice the payload without checking the actual
  payload length, causing an `IndexError` on truncated data. Added length validation.

- **Client handshake timeout config ignored**: `ThreadingSocket._handle_server_client()`
  used a hardcoded timeout instead of `self.handshake_timeout`. Now uses the config value.

- **`BaseSocket` imported at runtime**: `Client.__init__()` imported `BaseSocket`
  at the top level, causing circular import errors. Now imported inside the method.

#### Logger

- **`_rotate_file()` missing lock**: file rotation could race with concurrent writes
  from other threads, writing to a closed file handle. Now fully locked.

- **Logger config read/write race**: `_log()` read `self.config.*` without holding
  the lock, so a concurrent `configure()` could change values mid-read. All config
  reads are now inside `self._lock`.

- **`get_instance()` accepted a misleading `config` param** then silently ignored it
  on subsequent calls. Replaced with explicit `configure()` method and `config` param
  on first call only.

- **User `LoggerConfig.file_path` mutated**: `Writer.__init__()` assigned
  `self.file_path = config.file_path` then replaced it with a `Path` object,
  altering the caller's config. Now stores the internal copy as `self._file_path`.

- **`file_rotation_size` / `file_backup_count` not validated**: negative or zero
  values caused silent failures. Added `__post_init__` validation in `LoggerConfig`.

#### Sender

- **Socket not invalidated on `ConnectionResetError`/`BrokenPipeError`**: the
  `Sender` caught these exceptions during `send()` but kept `self.conn` pointing
  to the dead socket. Now sets `self.conn = None` when caught in CLIENT mode.

#### Benchmark

- **Off-by-one in percentile calculation**: `LatencyStats.percentile()` used
  `int(len(s) * pct / 100)` as index, returning the 0th element for 0th percentile
  and the n-1th for 100th, rather than clamping properly. Fixed with
  `min(int(len(s) * pct / 100), len(s) - 1)`.

- **Memory leak report used `abs()` delta**: the teardown delta was displayed as
  `abs(leak)`, so negative values (memory freed below baseline) appeared identical
  to positive leaks. Now displays the signed delta.

- **Logger configured at module level**: `velix.benchmark.__main__` configured the
  logger at import time, causing side effects on import. Moved into the `__main__`
  guard.

#### Types / Misc

- **`MessageTypeRegistry.register()` not thread-safe**: concurrent `MessageType()`
  construction could create duplicate code entries. Now locked with `threading.Lock()`.

- **`Version.__repr__` used dots instead of commas**: `__repr__` returned
  `Version(1.6.6)` (dots), making it look like a dotted version string rather
  than distinct constructor arguments. Fixed to `Version(1, 6, 6)` (commas)
  for clarity.

- **RuntimeError on executor submit after shutdown**: `CallbackExecutor.submit()`
  raised `RuntimeError` when called after `shutdown()`. Now caught and logged.

- **`UnhandledRule.handle()` crashed on `None` client**: when `context.client` was
  `None`, `getattr(context.client, "addr", ...)` failed. Now guarded.

- **Return type annotations used `socket.socket` instead of `BaseSocket`** in
  `Server` and `ClientsManager` method signatures. Fixed to `BaseSocket`.

- **`Response.latency` and `Response.timestamp` fields removed**: these were calculated
  from `time.time()` but never used by any internal path. Latency is measured by the
  ping methods using `time.perf_counter()` directly.

### Added

- **`HEADER_SIZE` constant**: replaces the magic number `14` in `MessageBuffer` and
  `Request.parse()` / `compile()`. Exported from `veltix.network.request`.

- **`jitter_ms` and `throughput` fields on `LatencyStats`**: the benchmark latency
  stats dataclass now carries these computed values, making them available for JSON
  export via `to_dict()`.

- **`recv_gap_avg_ms` on `BurstResult`**: the average gap between consecutive receives
  (inter-arrival time), computed in the burst benchmark but previously not stored.

- **`try_handle()` on `PendingRequestRule`**: new method that atomically checks and
  dispatches to a pending request queue, eliminating the TOCTOU race window.

- **`context_get_socket()` on `ClientContext` protocol**: allows the reconnect handler
  to close the socket when cancelling a mid-connect retry.

### Changed

- **Burst benchmark metric rename**: `recv_lat_p50/95/99/max/jitter` renamed to
  `drain_p50/95/99/max/jitter` and `recv_lat_jitter` to `drain_jitter_ms`, reflecting
  that these measure pipeline drain latency, not network latency.

- **Ping RTT measurement**: `ping_server()` and `ping_client()` now use
  `time.perf_counter()` instead of `time.time()`, avoiding negative latency readings
  from NTP clock adjustments.

### Internal

- **`RecvResult` is no longer a singleton**: every `recv()` call returns a fresh
  instance.
- **Logger `_stats` dict uses `dict.fromkeys(LogLevel, 0)`**: ensures all log levels
  are present in stats even if never logged.

### Tests

- **`test_message_buffer.py`**: added `test_resync_after_corrupt_message` verifying
  that `extract_messages()` advances past a corrupt frame and continues parsing.
- **`test_compatibility.py`**: `test_platform_internals` ensures compatibility table
  is restored after temporary modification (test isolation fix).

### Documentation

- **Performance metrics updated** for Python 3.14.5 with revised benchmark results.
- **All PerformanceMode references removed** from migration guides and docs.

### Migration Guide

#### v1.6.9 → v1.6.10

##### PerformanceMode removed

`PerformanceMode` enum and `ServerConfig.performance_mode` / `ClientConfig.performance_mode` no longer exist.
The socket timeout is now hardcoded to **0.5 s** (equivalent to the old `BALANCED` preset).

```python
# Before (v1.6.9)
from veltix import PerformanceMode
from veltix import ServerConfig

config = ServerConfig(host="0.0.0.0", port=8080, performance_mode=PerformanceMode.HIGH)

# After (v1.6.10) — remove the parameter entirely
config = ServerConfig(host="0.0.0.0", port=8080)
```

##### `@route` server callback order

Server route callbacks now receive `(client, response)` matching `on_recv`, instead of `(response, client)`.

```python
# Before (v1.6.9)
@server.route(MY_TYPE)
def handler(response: Response, client: ClientInfo):
    ...


# After (v1.6.10)
@server.route(MY_TYPE)
def handler(client: ClientInfo, response: Response):
    ...
```

##### `Response.latency` and `Response.timestamp` removed

These fields were always `0.0` / `None` in practice — they were never populated by the wire protocol.
Use the ping methods (`ping_server()` / `ping_client()`) which measure RTT via `time.perf_counter()`.

##### `Server.clients` returns `list[ClientInfo]`

The `clients` property no longer returns internal `ClientEntry` objects. If you were accessing
`.info` manually on entries, drop it:

```python
# Before (v1.6.9)
server.clients[0].info.addr

# After (v1.6.10)
server.clients[0].addr
```

## [1.6.9] - 2026-06-03

### Fixed

- **Routes preserved across reconnection** — `ReconnectHandler.reset()` was re-creating the
  `RequestHandler` without re-registering existing routes, silently losing all `@client.route()`
  handlers after automatic reconnection. Now saves and restores them.

- **`MessageBuffer(None)` TypeError** — `ClientsManager` passed `None` as `max_message_size`
  to `MessageBuffer` when no argument was given, overriding the 10 MB default and causing
  `extract_messages()` to crash with `TypeError`. Now falls back to 10 MB when `None`.

- **Initial `on_disconnect` not fired when `retry > 0`** — `try_reconnect()` skipped the
  initial `on_disconnect(permanent=False)` event when auto-reconnect was enabled, diverging
  from documented behaviour. Now fires the initial disconnection event before entering the
  reconnect loop.

- **`retry()` could start parallel reconnect loops** — calling `client.retry()` multiple
  times launched concurrent threads, each competing to reconnect. Now guards against
  overlapping loops via a thread reference + `is_alive()` check.

- **`thread_handler` never joined in `close_all()`** — `close_all()` (aliased as `close()`
  for client mode) joined `start_th` but not `thread_handler`, leaving the receive thread
  alive until the socket error forced it out. Now joins `thread_handler` with proper
  `None` guard and `current_thread` check.

- **Missing attributes in `_create_client_instance()`** — server-side client socket
  instances created via `_create_client_instance()` were missing `start_th`, `threads`,
  `_threads_lock`, `n_th`, `_n_th_lock`, and `thread_handler`, causing silent
  `AttributeError` in `close_all()`. All attributes are now properly initialized.

- **Stale `running=True` on `_accept_loop` exception** — when `_accept_loop` exited on
  `OSError` or unexpected exception, `self.running` remained `True`, making the server
  appear active. Now sets `self.running = False` before each early return.

### Changed

- **Time source for latency timestamps** — `Request.parse()` and `Request.compile()` now
  use `time.monotonic()` instead of `time.time()` to avoid negative latency readings when
  the system clock is adjusted (NTP).

### Removed

- **Dead `ping_result` attribute** from `Server` — was declared in `__slots__` and
  initialized to `None` but never read or written.

- **Redundant `_handshake_done` initialisation** in `Client.__init__()` — was set to `None`
  then immediately overwritten by `init_components()`. Now initialised as `Event()` directly.

- **Magic number `settimeout(0.5)`** in `ThreadingSocket.__init__()` — this value was
  immediately overwritten by subsequent `settimeout()` calls from the performance mode
  settings.

### Internal

- **Guarded `psutil` import** in `benchmark/cli.py` — now wrapped in `try/except ImportError`
  with a clear message instructing users to install `veltix[benchmark]`.

## [1.6.8] - 2026-05-20

### Added

- **`ClientContext` Protocol** in `veltix.client.reconnect_handler`
    - `ReconnectHandler` now accepts a single `context: ClientContext` instead of 8 individual callbacks
    - `Client` implements `ClientContext` natively via `context_*` methods
    - `refresh()` removed : no more stale lambda captures after `init_components()`
    - `init_components()` no longer has side effects on `ReconnectHandler`

- **Rules system** in `veltix.handler`
    - `Rule` ABC with `can_handle(context)` and `handle(context)` : extend to add custom dispatch logic
    - `RulesManager` : ordered rule pipeline, stops at first match
    - `MessageContext` dataclass : encapsulates `response`, `handler`, `client`, `is_server`
    - Built-in rules in priority order : `PingRule`, `HelloRule`, `PendingRequestRule`, `RouteRule`, `OnRecvRule`,
      `UnhandledRule`
    - `RequestHandler.handle()` reduced to a single `rules_manager.process(ctx)` call

### Changed

- **`RequestHandler.handle()`** refactored : monolithic `if/elif` chain replaced by the Rules pipeline
- **`ReconnectHandler`** constructor simplified from 8 parameters to `context: ClientContext`
- **`init_components()`** in `Client` no longer rebuilds `ReconnectHandler` on every call : instantiated once, never
  refreshed

### Removed

- **`ReconnectHandler.refresh()`** : made obsolete by `ClientContext` Protocol
- **`set_running()`** and **`set_connected()`** standalone methods on `Client` : replaced by `context_set_running()` and
  `context_set_connected()`

### Documentation

- README rewritten : new pitch, cleaner structure, external files for roadmap, performance, and migration
- `ROADMAP.md` created : full version history and planned releases
- `PERFORMANCE.md` created : detailed benchmark results and methodology
- `docs/index.md` updated : aligned with new README
- `docs/guides/migration.md` updated : added v1.6.6 to v1.6.7 section

## [1.6.6] - 2026-05-16

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

- **Reconnect tests** (`test_reconnect.py`): even with `close_all` ordering fixed, a brief kernel
  race (SO_REUSEADDR) could let a phantom TCP connect succeed against the dying port.
  `is_connected=True` was set before the handshake, making `_wait_for_connect` return a false
  positive. Added `_wait_for_reconnect()` that polls the actual ON_CONNECT callback count, and
  reduced `handshake_timeout` to 1s so phantom attempts fail fast.

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
