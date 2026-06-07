# Roadmap

## Released

### v1.0.0 : Initial Release *(February 2026)*

- TCP Server with multi-threading support
- TCP Client with event-driven callbacks
- Binary protocol with SHA256 integrity verification
- Custom `MessageType` system
- Event binding system (`ON_RECV`, `ON_CONNECT`)
- Zero dependencies : pure Python stdlib

### v1.4.0 : Handshake & Callbacks *(March 2026)*

- HELLO/HELLO_ACK handshake with version compatibility check
- Thread pool for non-blocking callback execution (`CallbackExecutor`)
- Blocking `connect()` : safe to send immediately after connecting
- `on_connect` / `on_disconnect` callbacks on Client

### v1.5.0 : Routing & Auto-Reconnect *(March 2026)*

- Decorator-based message routing (`@server.route(MY_TYPE)`, `@client.route(MY_TYPE)`)
- Auto-reconnect with configurable retry and `DisconnectState` callbacks
- `BufferSize` presets for common buffer configurations

### v1.6.0 : Socket Abstraction & Tags *(March 2026)*

- `BaseSocket` Protocol : universal socket interface
- `ThreadingSocket` : current implementation behind clean abstraction
- `SocketCore` enum : swappable socket backends with zero API changes
- `ClientInfo` tags : arbitrary metadata on connected clients
- `veltix.utils` : encoding helpers and `format_bytes`
- `max_connection = -1` : unlimited connections by default
- Benchmark suite with JSON export

### v1.6.3 : Benchmark Refactor *(April 2026)*

- Full benchmark module refactor into a clean, reusable package
- Extended result models with leak detection, tick accuracy, per-client throughput
- Run via `python -m veltix.benchmark`

### v1.6.4 : ClientsManager & Socket Restructure *(May 2026)*

- Centralized `ClientsManager` with thread-safe `ClientEntry`
- Socket module restructured : `veltix/socket/` to `veltix/socket_core/`
- `close_client()` with `ClientEntry` / int ID support

### v1.6.5 : Client Management & Tag Filtering *(May 2026)*

- `close_client()` exposed on `Server`
- `get_clients_by_tag()` on `Server` and `ClientsManager`
- `to_sockets()` on `ClientsManager`

### v1.6.6 : Version Compatibility & Reconnect Stability *(May 2026)*

- `Version` class + `COMPATIBILITY` table
- 4 reconnect core fixes
- +111 new tests
- CI on Python 3.8 / 3.10 / 3.12 / 3.14

### v1.6.8 : Architecture Refactor *(May 2026)*

- `ClientContext` Protocol : replaces callback soup in `ReconnectHandler`
- Rules system for `RequestHandler` : scalable, readable message dispatch
- README rewrite + documentation restructure

### v1.6.9 : Reconnect Stability & Cleanup *(June 2026)*

- 8 bug fixes across the reconnect path (routes lost, thread_handler not joined, etc.)
- Switched latency timestamps from `time.time()` to `time.monotonic()`
- Removed dead code : `ping_result`, redundant `_handshake_done`, magic `settimeout(0.5)`
- Guarded `psutil` import in benchmark CLI

---

## Planned

### v1.7.0 : Selectors *(June 2026)*

- `AsyncSocket` : selectors-based I/O, replaces one-thread-per-client
- Same API, 4-8x throughput improvement expected
- Switch via `SocketCore.ASYNC`

### v1.8.0 : Plugin System *(August 2026)*

- `VeltixBasePlugin` : extensible plugin architecture
- Permission system for plugin event access
- `server.register_plugin()` / `client.register_plugin()`

### v2.0.0 : Encryption *(September 2026)*

- End-to-end encryption : ChaCha20 + X25519 + Ed25519
- Automatic key exchange and perfect forward secrecy

### v3.0.0 : Rust Core *(2027)*

- PyO3 bindings
- 10-100x throughput improvement
- `SocketCore.RUST`