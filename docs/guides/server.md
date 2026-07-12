# Server Guide

## Configuration

```python
from veltix import Server, ServerConfig, BufferSize

config = ServerConfig(
    host="0.0.0.0",  # Listening address
    port=8080,  # Listening port
    buffer_size=BufferSize.SMALL,  # Receive buffer size (default: 1KB)
    max_connection=10,  # Max simultaneous clients
    max_message_size=10 * 1024 * 1024,  # 10MB max message size
    handshake_timeout=5.0,  # Handshake timeout in seconds
    max_workers=4,  # Thread pool size for callbacks
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
    print(f"[{client.addr[0]}] {response.content.decode()}")


@server.route(STATUS)
def on_status(client, response):
    print(f"Status from {client.addr[0]}: {response.content.decode()}")
```

Routes can also be registered and removed programmatically:

```python
server.request_handler.register_route(CHAT, on_chat)
server.request_handler.unregister_route(CHAT)
```

## Callbacks

```python
from veltix import Events

server.set_callback(Events.ON_CONNECT, lambda client: print(f"Connected: {client.addr}"))
server.set_callback(Events.ON_RECV, lambda client, msg: print(msg.content.decode()))
server.set_callback(Events.ON_DISCONNECT, lambda client: print(f"Disconnected: {client.addr}"))
```

!!! note
`on_connect` fires only after the handshake is complete. `client.handshake_done` is always `True` when it fires.

!!! tip
Use `@server.route()` for per-type handlers. `on_recv` is the fallback for unrouted messages.

## Sending messages

```python
# Send to a specific client
server.sender.send(request, client=client.conn)

# Broadcast to all clients
server.sender.broadcast(request, server.get_all_clients_sockets())

# Broadcast with exclusion
server.sender.broadcast(request, server.get_all_clients_sockets(), except_clients=[client.conn])
```

## Ping

```python
# Synchronous
latency = server.ping_client(client, timeout=2.0)

# Asynchronous (safe from within on_connect)
server.ping_client_async(client, callback=lambda ms: print(f"{ms}ms"), timeout=2.0)
```

## Shutdown

```python
server.close_all()
```
