# Routing

Message routing lets you handle specific message types with dedicated callbacks, without a global `on_recv`. Routes take
priority over `on_recv` and run in the thread pool.

## Server routing

```python
from veltix import Server, ServerConfig, MessageType, Response, ClientInfo

CHAT = MessageType(code=200, name="chat")
STATUS = MessageType(code=201, name="status")

server = Server(ServerConfig(host="0.0.0.0", port=8080))


@server.route(CHAT)
def on_chat(client: ClientInfo, response: Response):
    print(f"[{client.addr[0]}] {response.content.decode()}")


@server.route(STATUS)
def on_status(client: ClientInfo, response: Response):
    print(f"Status from {client.addr[0]}: {response.content.decode()}")


server.start()
```

## Client routing

```python
from veltix import Client, ClientConfig, MessageType, Response

CHAT = MessageType(code=200, name="chat")

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))


@client.route(CHAT)
def on_chat(response: Response, client=None):
    print(f"Server: {response.content.decode()}")


client.connect()
```

## Priority over on_recv

Routes take priority over the global `on_recv`. If a message matches a route, `on_recv` is **not** called.

```
message received
    → route matches? → call route callback
    → no route?      → call on_recv (if set)
    → no on_recv?    → log warning, drop
```

```python
@server.route(CHAT)
def on_chat(response, client):
    ...  # called for CHAT messages


server.set_callback(Events.ON_RECV, fallback)  # called for everything else
```

## Programmatic registration

```python
# Register
server.request_handler.register_route(CHAT, on_chat)  # returns False if already registered

# Unregister — falls back to on_recv after this
server.request_handler.unregister_route(CHAT)  # returns False if not registered
```

## Thread pool

Route callbacks run in the same thread pool as `on_recv` — a slow route handler never blocks the recv loop.

!!! warning
Registering the same type twice returns `False` and keeps the original. Unregister first if you want to replace a route.
