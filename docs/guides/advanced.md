# Advanced Features

## Broadcasting

```python
# Broadcast to all connected clients
message = Request(CHAT, b"Server announcement")
sender.broadcast(message, server.get_all_clients_sockets())

# Broadcast with exclusion
sender.broadcast(message, server.get_all_clients_sockets(), except_clients=[client.conn])
```

## Client Tags

Attach arbitrary metadata to connected clients for tracking, filtering, or access control.

```python
from veltix import Server, ServerConfig, ClientInfo, Events

server = Server(ServerConfig(host="0.0.0.0", port=8080))


def on_connect(client: ClientInfo):
    client.add_tag("guest")


def on_message(client: ClientInfo, response):
    if client.has_tag("guest"):
        client.remove_tag("guest")
        client.add_tag("authenticated", value="admin")

    if client.has_all_tags(["authenticated", "admin"]):
        print(f"Admin message from {client.addr[0]}")


server.set_callback(Events.ON_CONNECT, on_connect)
server.set_callback(Events.ON_RECV, on_message)
server.start()
```

Available tag methods on `ClientInfo`:

```python
client.add_tag("authenticated")               # Add a tag (returns False if already exists)
client.add_tag("role", value="admin")          # Add a tag with a value
client.has_tag("authenticated")                # Check for a single tag
client.has_all_tags(["auth", "admin"])         # Check all tags are present (AND)
client.has_any_tags(["admin", "mod"])          # Check at least one tag is present (OR)
client.get_tag("role")                         # Retrieve a tag value
client.remove_tag("guest")                     # Remove a tag
client.clear_tags()                            # Remove all tags
```

## Socket Backend

Veltix abstracts the socket layer behind a `SocketCore` enum. The default is `THREADING` — future versions will add
`ASYNC` (selectors-based, v1.7.0) and `RUST` (Tokio via PyO3, v3.0.0).

```python
from veltix import ServerConfig, ClientConfig, SocketCore

# Default — one thread per client
server = Server(ServerConfig(host="0.0.0.0", port=8080, socket_core=SocketCore.THREADING))

# Coming in v1.7.0 — selectors-based, same API
# server = Server(ServerConfig(host="0.0.0.0", port=8080, socket_core=SocketCore.ASYNC))
```

Switching backends requires no changes to application code.

## Buffer Size

```python
from veltix import ServerConfig, ClientConfig, BufferSize

# SMALL  — 1KB  (default)
# MEDIUM — 8KB
# LARGE  — 64KB
# HUGE   — 1MB

server = Server(ServerConfig(host="0.0.0.0", port=8080, buffer_size=BufferSize.LARGE))
```

## Custom Message Types

Message type codes are divided into ranges by convention:

```python
from veltix import MessageType

# System messages (0–199)
PING = MessageType(0, "ping", "System ping")

# Application messages (200–499)
CHAT = MessageType(200, "chat", "Chat message")
FILE_TRANSFER = MessageType(201, "file", "File transfer")

# Plugin messages (500+)
CUSTOM = MessageType(500, "plugin", "Custom plugin message")
```

## Configuring the Thread Pool

```python
from veltix import ServerConfig, ClientConfig

# Increase workers for high-concurrency workloads with slow callbacks
server_config = ServerConfig(host="0.0.0.0", port=8080, max_workers=8)
client_config = ClientConfig(server_addr="127.0.0.1", port=8080, max_workers=8)
```

## Utilities

```python
from veltix import format_bytes, encode_json, decode_json, encode_utf8, decode_utf8

# Human-readable byte formatting
format_bytes(148_000)    # "144.5 KB"
format_bytes(3_000_000)  # "2.86 MB"

# JSON helpers
data = encode_json({"key": "value"})  # bytes
obj = decode_json(data)               # dict

# UTF-8 helpers
raw = encode_utf8("hello")  # bytes
text = decode_utf8(raw)     # str
```
