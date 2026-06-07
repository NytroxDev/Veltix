# Migration Guide

## v1.6.9 → v1.6.10

**Breaking changes in public API :**

### `PerformanceMode` removed

`PerformanceMode` enum and `ServerConfig.performance_mode` / `ClientConfig.performance_mode` no longer exist. The socket
timeout is now hardcoded. If you were setting a performance mode, remove that configuration.

```python
# Before (v1.6.9)
from veltix import PerformanceMode

config = ServerConfig(host="0.0.0.0", port=8080, performance_mode=PerformanceMode.HIGH)

# After (v1.6.10) — just remove the parameter
config = ServerConfig(host="0.0.0.0", port=8080)
```

### `@server.route` callback order flipped

Server route callbacks now receive `(client, response)` instead of `(response, client)`. Client routes
(`@client.route`) are unaffected — they still use `(response, client=None)`.

```python
# Before (v1.6.9)
@server.route(CHAT)
def on_chat(response, client):
    ...

# After (v1.6.10)
@server.route(CHAT)
def on_chat(client, response):
    ...
```

### `Response.latency` and `Response.timestamp` removed

The `latency` and `timestamp` fields have been removed from `Response`. Use `client.ping_server()` /
`server.ping_client()` for latency measurement instead.

```python
# Before (v1.6.9)
response = client.send_and_wait(request, timeout=5.0)
print(f"{response.latency:.2f}ms")

# After (v1.6.10)
response = client.send_and_wait(request, timeout=5.0)
print(f"Got: {response.content.decode()}")
```

### `server.clients` now returns `list[ClientInfo]`

The `clients` property on `Server` now returns `list[ClientInfo]` directly instead of internal `ClientEntry` objects.
Access patterns are simplified :

```python
# Before (v1.6.9)
entry = server.clients[0]
entry.info.conn         # client connection
entry.info.addr         # client address

# After (v1.6.10)
client = server.clients[0]
client.conn             # client connection (same)
client.addr             # client address (same)
client.handshake_done   # handshake status (same)
```

## v1.6.6 → v1.6.8

No breaking changes to public API.

**Internals refactored :**

- `ReconnectHandler` now takes a single `ClientContext` Protocol instead of 8 individual callbacks
- `RequestHandler.handle()` now uses a Rules system internally : `PingRule`, `HelloRule`, `PendingRequestRule`,
  `RouteRule`, `OnRecvRule`, `UnhandledRule`

These are internal architecture changes only. No changes required in your application code.

## v1.6.0 → v1.6.4

No breaking changes since v1.6.2. The `socket_core` module renamed from `veltix.socket` to `veltix.socket_core` does not
affect the public API : all exports go through `veltix/__init__.py`.

### `server.clients` now returns `list[ClientEntry]`

If you iterate over `server.clients`, update access patterns:

```python
# Before (v1.6.3 and earlier)
client = server.clients[0]
client.conn  # raw socket
client.handshake_done  # bool

# After (v1.6.4)
entry = server.clients[0]
entry.info.conn  # client connection
entry.info.handshake_done  # handshake status
entry.buffer  # MessageBuffer
entry.id  # client ID
```

!!! note
    `ClientEntry` was replaced by `ClientInfo` in v1.6.10. See the **v1.6.9→v1.6.10** section above for the current access
    pattern.

## v1.6.0 → v1.6.2

Breaking changes in protocol/API:

- `request_id` is now `bytes` (4 bytes), not UUID string
- Wire format changed (header/hash/request_id), upgrade both client/server together
- Handshake version check now requires exact `major.minor.patch` match
- Minimum supported Python version is now **3.8+**

### Custom request id migration

```python
# Before
Request(T, b"x", request_id="my-id")

# After
Request(T, b"x", request_id=b"\x01\x02\x03\x04")
```

### Logging/display migration

```python
# Before
response.request_id[:8]

# After
response.request_id.hex()[:8]
```

## v1.5.0 → v1.6.0

No breaking changes to public API.

- `ClientInfo` now has tag methods: `add_tag()`, `has_tag()`, `has_all_tags()`, `has_any_tags()`, `get_tag()`,
  `remove_tag()`, `clear_tags()`
- `ServerConfig.max_connection` default changed from `2` to `-1` (unlimited)
- New `ServerConfig` / `ClientConfig` field: `socket_core` (default: `SocketCore.THREADING`)
- `veltix.utils` now exports encoding helpers and `format_bytes`
- Benchmark suite now supports `--save results.json`

## v1.4.0 → v1.5.0

**Breaking change:** `on_disconnect` on the client now receives a `DisconnectState` argument.

```python
# Before (v1.4.0)
client.set_callback(Events.ON_DISCONNECT, lambda: print("Disconnected"))

# After (v1.5.0)
client.set_callback(Events.ON_DISCONNECT, lambda state: print(f"Disconnected — permanent={state.permanent}"))
```

New optional fields in `ClientConfig`: `retry`, `retry_delay`, `buffer_size`.

New optional fields in `ServerConfig`: `buffer_size`.

## v1.3.0 → v1.4.0

No breaking changes to public API.

- `on_connect` (server-side) now fires after the handshake is complete — `client.handshake_done` is always `True` when
  it fires.
- `connect()` (client-side) now blocks until the handshake is done. It is safe to send messages immediately after it
  returns.
- New `ClientConfig` fields: `handshake_timeout` (default: `5.0`), `max_workers` (default: `4`)
- New `ServerConfig` fields: `handshake_timeout` (default: `5.0`), `max_workers` (default: `4`)

## v1.2.x → v1.3.0

No breaking changes to public API.

## v1.1.x → v1.2.0

```python
# Before
from veltix import Bindings

server.bind(Bindings.ON_RECV, callback)

# After
from veltix import Events

server.set_callback(Events.ON_RECV, callback)
```
