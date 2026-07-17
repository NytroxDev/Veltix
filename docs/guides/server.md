# Server Guide

## Configuration

```python
from veltix import Server, ServerConfig, BufferSize, SocketCore

config = ServerConfig(
    host="0.0.0.0",  # Listening address
    port=8080,  # Listening port
    buffer_size=BufferSize.SMALL,  # Receive buffer size (default: 1KB)
    max_connection=-1,  # Max simultaneous clients (-1 = unlimited)
    max_message_size=10 * 1024 * 1024,  # 10MB max message size
    handshake_timeout=5.0,  # Handshake timeout in seconds
    max_workers=4,  # Thread pool size for callbacks
    socket_core=SocketCore.ASYNC,  # Socket backend (default: ASYNC)
    id_window=30000,  # Unique IDs per direction (default: 30000)
)

server = Server(config)
```

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
    print(f"[{client.addr[0]}] {response.text}")


@server.route(STATUS)
def on_status(client, response):
    print(f"Status from {client.addr[0]}: {response.text}")
```

Routes can also be registered and removed programmatically:

```python
server.request_handler.register_route(CHAT, on_chat)
server.request_handler.unregister_route(CHAT)
```

## Callbacks

```python
server.on_connect(lambda client: print(f"Connected: {client.addr}"))
server.on_recv(lambda client, msg: print(msg.text))
server.on_disconnect(lambda client: print(f"Disconnected: {client.addr}"))
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
server.close_all()
server.wait_until_closed()  # block until shutdown
```

## Restart

```python
server.restart()  # stop + start, preserves routes and callbacks
```
