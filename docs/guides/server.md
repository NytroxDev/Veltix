# Server Guide

## Configuration

```python
from veltix import Server, ServerConfig, BufferSize, SocketCore

config = ServerConfig(
    host="0.0.0.0",  # Listening address
    port=8080,  # Listening port
    buffer_size=BufferSize.MEDIUM,  # Receive buffer size (default: 8KB)
    max_connection=-1,  # Max simultaneous clients (-1 = unlimited)
    max_message_size=10 * 1024 * 1024,  # 10MB max message size
    handshake_timeout=5.0,  # Handshake timeout in seconds
    max_workers=4,  # Thread pool size for callbacks
    socket_core=SocketCore.ASYNC,  # Socket backend (default: ASYNC)
    id_window=30000,  # Pending request-ID window per direction (default: 30000)
)

server = Server(config)
```

!!! note
    `id_window` accepts `1..65535` but is clamped to `32768` at startup: the upper half of the 16-bit
    ID space is reserved for the client's outgoing requests. See
    [Request-ID Correlation](../design/request-id-correlation.md).

## Starting the server

```python
server.start()  # Non-blocking, runs in background thread
```

## Routing

Use `@server.route()` to handle specific message types directly. Routes take priority over `on_recv` and run in the
thread pool.

```python
from veltix import MessageType, Request

CHAT = MessageType("chat")
STATUS = MessageType("status")


@server.route(CHAT)
def on_chat(client, response):
    print(f"[{client.ip}] {response.text}")


@server.route(STATUS)
def on_status(client, response):
    print(f"Status from {client.ip}: {response.text}")
```

Routes can also be registered and removed programmatically:

```python
server.request_handler.register_route(CHAT, on_chat)
server.request_handler.unregister_route(CHAT)
```

See the [Routing guide](routing.md) for full details.

## Callbacks

```python
server.on_connect(lambda client: print(f"Connected: {client.ip}:{client.port}"))
server.on_recv(lambda client, msg: print(msg.text))
server.on_disconnect(lambda client: print(f"Disconnected: {client.ip}:{client.port}"))
```

!!! note
    `on_connect` fires only after the handshake is complete. `client.handshake_done` is always `True` when it fires.

!!! tip
    Use `@server.route()` for per-type handlers. `on_recv` is the fallback for unrouted messages.

## Sending messages

```python
# Send to a specific client
server.send(request, client)

# Broadcast to all clients
server.broadcast(request)

# Broadcast with exclusion
server.broadcast(request, except_clients=[client])
```

## Ping

```python
latency = server.ping_client(client, timeout=2.0)
```

## Shutdown

```python
server.start()
server.wait_until_closed()  # blocks until close_all() is called (Ctrl+C works too)
```

`close_all()` stops the server and disconnects every client without blocking; call it from a signal
handler, a route, or another thread. `wait_until_closed()` is what keeps the main thread alive.

## Restart

```python
server.restart()  # stop + start, preserves routes and callbacks
```
