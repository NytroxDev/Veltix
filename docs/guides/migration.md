# Migration Guide

## v1.9.0 → v2.0.0

**Breaking changes in wire protocol and public API — NOT backward compatible.**

!!! danger
    v2.0.0 **cannot communicate** with v1.9.x. Upgrade both client and server together.

### Wire protocol (15-byte header)

The header size has been reduced from 16 to 15 bytes. The new layout:

```
Before (v1.9.0) : [2B MAGIC][2B size][2B code][4B CRC][4B request_id][content]
After  (v2.0.0) : [2B MAGIC][1B flags][2B code][4B size][4B CRC][2B request_id][content]
                   ^^^^^^^^ ^^^^^^^^                                     ^^^^^^^^^^
                   VX       NEW — reserved                               2 bytes (was 4)
```

### `request_id` is now `int` (not `bytes`)

The biggest API change: `request_id` went from 4-byte `bytes` to 2-byte `int` (uint16).

```python
# ── Before (v1.x) ──────────────────────────────────────────
from veltix import Request

request = Request(MY_TYPE, b"hello", request_id=b"\x01\x02\x03\x04")
print(response.request_id.hex())     # "01020304"
print(response.request_id[:2])       # b'\x01\x02'

# ── After (v2.0) ───────────────────────────────────────────
request = Request(MY_TYPE, b"hello", request_id=42)
print(response.request_id)          # 42
print(hex(response.request_id))     # '0x2a'
```

#### Correlation pattern (send_and_wait)

```python
# ── Before (v1.x) ──────────────────────────────────────────
from veltix import generate_random_id

req = Request(ECHO, b"ping", request_id=generate_random_id())
server.send_and_wait(req, client, timeout=5.0)

# ── After (v2.0) ───────────────────────────────────────────
# generate_random_id() is gone — IDAllocator handles it automatically
req = Request(ECHO, b"ping")  # request_id auto-allocated
server.send_and_wait(req, client, timeout=5.0)
```

#### Responding to a request (echo pattern)

```python
# ── Before (v1.x) ──────────────────────────────────────────
@server.route(ECHO)
def on_echo(client, response):
    reply = Request(ECHO, response.content, request_id=response.request_id)
    server.send(reply, client)

# ── After (v2.0) ───────────────────────────────────────────
@server.route(ECHO)
def on_echo(client, response):
    reply = Request(ECHO, response.content, request_id=response.request_id)
    server.send(reply, client)
```

#### Logging request IDs

```python
# ── Before (v1.x) ──────────────────────────────────────────
logger.info(f"Ping from {client.addr}: id={response.request_id.hex()}")

# ── After (v2.0) ───────────────────────────────────────────
logger.info(f"Ping from {client.addr}: id={response.request_id}")
```

#### Removing `generate_random_id` imports

```python
# ── Before (v1.x) ──────────────────────────────────────────
from veltix.network.request import generate_random_id

request_id = generate_random_id()

# ── After (v2.0) ───────────────────────────────────────────
# Delete the import entirely — not needed anymore.
# If you want a specific ID, just pass an int:
request_id = 42
```

#### `REQUEST_ID_SIZE` constant

```python
# ── Before (v1.x) ──────────────────────────────────────────
from veltix.network.request import REQUEST_ID_SIZE  # was 4

# ── After (v2.0) ───────────────────────────────────────────
from veltix.network.request import REQUEST_ID_SIZE  # now 2
```

### `ServerConfig.id_window` added

The server now sends an `id_window` parameter in the handshake meta, telling each client
how many unique IDs are available in each direction.

```python
# ── Before (v1.x) ──────────────────────────────────────────
server = Server(ServerConfig(port=8080))

# ── After (v2.0) ───────────────────────────────────────────
# Same — id_window defaults to 30000
server = Server(ServerConfig(port=8080))

# Or customize — smaller window for constrained environments
server = Server(ServerConfig(port=8080, id_window=10000))

# The client receives this automatically during handshake:
# Server sends: {"v": "2.0.0", "meta": {"id_window": 30000}}
```

!!! tip
    30 000 IDs is enough for ~30 000 in-flight requests per connection. If you're doing
    high-throughput RPC with many concurrent requests, increase it. For simple use cases,
    the default is fine.

### `HEADER_SIZE` changed

```python
# ── Before (v1.x) ──────────────────────────────────────────
from veltix.network.request import HEADER_SIZE  # was 16

# ── After (v2.0) ───────────────────────────────────────────
from veltix.network.request import HEADER_SIZE  # now 15
```

If you use `HEADER_SIZE` for buffer calculations or manual framing, update accordingly.

### `Response._hash` is now private

```python
# ── Before (v1.x) ──────────────────────────────────────────
print(response.hash)      # b'\x3a\xfb...'

# ── After (v2.0) ───────────────────────────────────────────
print(response._hash)     # b'\x3a\xfb...'
```

!!! note
    This is a minor change — `_hash` is private but still accessible. If you were using
    `response.hash` for debugging, switch to `response._hash`.

### `MessageFlag` introduced (internal)

A new `MessageFlag(IntFlag)` enum is available for future compression/encryption support:

```python
from veltix.network.flags import MessageFlag

# Currently only one value:
MessageFlag.NONE  # 0x00
```

!!! warning
    `MessageFlag` is **not part of the public API**. It's reserved for internal protocol
    use. Don't rely on it in application code.

### `Sender` auto-allocates request IDs

The `Sender.send()` method now automatically allocates a `request_id` via `IDAllocator`
if none is provided:

```python
# ── Before (v1.x) ──────────────────────────────────────────
from veltix import Request, generate_random_id

req = Request(MY_TYPE, b"hello", request_id=generate_random_id())
server.sender.send(req, client)

# ── After (v2.0) ───────────────────────────────────────────
req = Request(MY_TYPE, b"hello")  # no request_id needed
server.sender.send(req, client)   # auto-allocated by IDAllocator
```

### Quick checklist

| What you used | What to do |
|---|---|
| `request_id=b"\x01\x02\x03\x04"` | Replace with `request_id=<int>` |
| `response.request_id` | Use `response.request_id` (int) |
| `response.request_id.hex()` | Use `str(response.request_id)` |
| `generate_random_id()` | Delete — auto-allocated now |
| `REQUEST_ID_SIZE = 4` | Now `2` — update if referenced |
| `HEADER_SIZE = 16` | Now `15` — update if referenced |
| `response.hash` | Use `response._hash` |
| `ServerConfig(...)` | Add `id_window=N` if needed (default: 30000) |

### Full before/after example

```python
# ══════════════════════════════════════════════════════════════
# BEFORE (v1.9.0)
# ══════════════════════════════════════════════════════════════
from veltix import Server, ServerConfig, Client, ClientConfig, MessageType, Request
from veltix.network.request import generate_random_id

ECHO = MessageType(200, "echo")
server = Server(ServerConfig(host="0.0.0.0", port=8080))

@server.route(ECHO)
def on_echo(client, response):
    # Echo back with same request_id
    reply = Request(ECHO, response.content, request_id=response.request_id)
    server.send(reply, client)
    print(f"Handled: id={response.request_id.hex()}")

server.start()

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))
client.connect()

req = Request(ECHO, b"ping", request_id=generate_random_id())
resp = client.send_and_wait(req, timeout=3.0)
if resp:
    print(f"Got: {resp.content.decode()}, id={resp.request_id.hex()}")

client.disconnect()
server.close_all()


# ══════════════════════════════════════════════════════════════
# AFTER (v2.0.0)
# ══════════════════════════════════════════════════════════════
from veltix import Server, ServerConfig, Client, ClientConfig, MessageType, Request

ECHO = MessageType("echo")  # auto-allocates code 200
server = Server(ServerConfig(host="0.0.0.0", port=8080))

@server.route(ECHO)
def on_echo(client, response):
    # Echo back with same request_id (now an int)
    reply = Request(ECHO, response.content, request_id=response.request_id)
    server.send(reply, client)
    print(f"Handled: id={response.request_id}")

server.start()

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))
client.connect()

req = Request(ECHO, b"ping")  # auto-allocated request_id
resp = client.send_and_wait(req, timeout=3.0)
if resp:
    print(f"Got: {resp.content.decode()}, id={resp.request_id}")

client.disconnect()
server.close_all()
```

---

## v1.8.0 → v1.8.1

**No breaking changes — wire-compatible with v1.8.0.**

v1.8.1 is a maintenance release focusing on bug fixes, type cleanup, and documentation.

### Changes

- **`Server.sender` and `Client.sender` are now properties** : `get_sender()` is deprecated
  and will be removed in a future version. Use `server.sender` and `client.sender` instead.
- **`BaseSocket` refactored from `Protocol` to `ABC`** : stronger inheritance guarantees.
  No user-facing changes required.
- **`PendingRequestRule.can_handle` now truthful** : no longer requires explicit
  `try_handle()` dispatch.
- **Handshake encode/decode exceptions no longer swallowed** : JSON errors now propagate.
- **`SO_REUSEADDR` moved to `bind()` only** : client sockets no longer inherit the option.
- **`handshake_timeout` propagated to client socket instances** : config was previously
  ignored on the client side.
- **AsyncSocket selector loop fixed** : no more busy-loop after self-disconnect.
- **Test suite ~7× faster** (49s → 7s) via `pytest-xdist`.
- **30 new unit tests**, 100% coverage on `Writer`.
- **Compatibility table** updated — both `1.8.0` and `1.8.1` are registered.

### Action required

- Migrate from `get_sender()` to `.sender` (deprecation warning, not a failure).

```python
# Before (v1.8.0)
server.get_sender().send(request, client=client.conn)

# After (v1.8.1)
server.sender.send(request, client=client.conn)
```

```python
# Before (v1.8.0)
client.get_sender().send(request)

# After (v1.8.1)
client.sender.send(request)
```

---

## v1.7.5 → v1.8.0

**Breaking change : handshake protocol — NOT backward compatible.**

v1.8.0 replaces the old HELLO/HELLO_ACK message-based handshake with a **JSON raw-socket
protocol**. Handshake now exchanges JSON payloads (`{"v": "1.8.0", "meta": {}}`) directly
over the TCP stream before any Veltix framing.

### Action required

- **All clients and servers must be upgraded together** — mixed-version handshakes will
  fail (v1.7.x sends a binary Veltix frame as HELLO, v1.8.0 expects a JSON payload).
- No source-level API changes needed — `client.connect()` still returns `bool`, the
  handshake is still automatic and transparent.
- `HELLO` / `HELLO_ACK` are no longer available as imports (they were never meant for
  public use).

### What changed

- Handshake is now **synchronous**: `connect()` blocks until the JSON handshake completes
  or the socket timeout fires. The internal `_handshake_done` Event has been removed.
- `HelloRule` removed — the handshake no longer routes through the message dispatch
  pipeline. This is an internal change only.
- `ERROR` / `INVALID_REQUEST` system types (codes 20, 21) are kept and re-exported.
- Compatibility table now includes `Version(1, 8, 0)` and `Version(1, 8, 1)`.

```python
# Before (v1.7.5) — HELLO/HELLO_ACK over Veltix wire protocol
# After (v1.8.0) — JSON over raw TCP, then normal Veltix protocol
# No code changes required.
```

---

## v1.7.1 → v1.7.2

**No breaking changes — wire-compatible with v1.7.0/v1.7.1.**

v1.7.2 is a stability release with 10 bug fixes, +108 tests, and documentation polish.
No protocol changes.

### Action required

None — drop-in upgrade.

```bash
pip install --upgrade veltix
```

---

## v1.7.0 → v1.7.1

**No breaking changes — wire-compatible with v1.7.0.**

v1.7.1 is a stability release with 6 bug fixes and no protocol changes.

### Changes

- **Fixed:** `AsyncSocket` selector idempotency on `_close_server_client`
- **Fixed:** `ClientInfo._id` with `__eq__`/`__hash__` for stable identity
- **Fixed:** daemon threads no longer block process exit
- **Fixed:** `close_client()` type hint corrected to `Optional[int]`
- **Fixed:** `send_and_wait` timeout compatibility with Python < 3.11
- **Fixed:** HELLO_ACK version validation in `_check_server_handshake`
- **New public exports:** `NetworkError`, `TimeoutError`

### Action required

None — drop-in upgrade.

```bash
pip install --upgrade veltix
```

---

## v1.6.10 → v1.7.0

**Breaking change : wire format — NOT backward compatible.**

v1.7.0 adds **2 MAGIC bytes** (`b"VX"`) at the start of every frame. The header size
increases from 14 to 16 bytes. v1.7.0 **cannot communicate** with earlier versions.

```
Before (v1.6.10) : [2B  size][2B  code][4B CRC][4B request_id][     content     ]
After  (v1.7.0)  : [2B MAGIC][2B  size][2B  code][4B CRC][4B request_id][content ]
                    ^^^^^^^^
                    new — always 0x56 0x58 ("VX")
```

### Action required

- **All clients and servers must be upgraded together** — mixed-version communication
  will fail with `RequestError("Invalid magic bytes")`.
- No source-level API changes needed — the wire format change is transparent to
  application code using `Request` / `Response` objects.

### New features

- **`AsyncSocket`** : selectors-based backend — switch via `SocketCore.ASYNC`.
  Up to **2x stress throughput** (76 929 msg/s vs 37 676 msg/s).
- **Protocol hardening** : MAGIC bytes, auto-resynchronization on corruption,
  `MAX_BUFFER_SIZE` (20 MB) for DoS protection.
- **Benchmark `--socket-core`** : test threading, async, or both side-by-side.
- **Benchmark `--runs N`** : average results over multiple runs.

See [CHANGELOG.md](../CHANGELOG.md) for the full list of changes.

---

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

- `request_id` changed from UUID string to `bytes` (4 bytes) — **NOTE: this was later changed to `int` (2 bytes) in v2.0.0**
- Wire format changed (header/hash/request_id), upgrade both client/server together
- Handshake version check now requires exact `major.minor.patch` match
- Minimum supported Python version is now **3.8+**

### Custom request id migration (v1.6.0 → v1.6.2)

```python
# Before (v1.5.x)
Request(T, b"x", request_id="my-id")

# After (v1.6.2)
Request(T, b"x", request_id=b"\x01\x02\x03\x04")  # bytes

# After (v2.0.0)
Request(T, b"x", request_id=42)  # int
```

### Logging/display migration (v1.6.0 → v1.6.2)

```python
# Before (v1.5.x)
response.request_id[:8]

# After (v1.6.2)
response.request_id.hex()[:8]

# After (v2.0.0) — request_id is now an int, not bytes
response.request_id  # just use the int directly
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
