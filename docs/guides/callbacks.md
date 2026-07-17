# Callbacks & Events

## Available events

| Event           | Server signature                                   | Client signature                   |
|-----------------|----------------------------------------------------|------------------------------------|
| `ON_CONNECT`    | `callback(client: ClientInfo)`                     | `callback()`                       |
| `ON_RECV`       | `callback(client: ClientInfo, response: Response)` | `callback(response: Response)`     |
| `ON_DISCONNECT` | `callback(client: ClientInfo)`                     | `callback(state: DisconnectState)` |

!!! note
Client `ON_DISCONNECT` now receives a [`DisconnectState`](reconnect.md) argument as of v1.5.0.

## Server callbacks

```python
from veltix import Server, ServerConfig

server = Server(ServerConfig(host="0.0.0.0", port=8080))

server.on_connect(lambda client: print(f"Connected: {client.addr}"))
server.on_recv(lambda client, msg: print(msg.text))
server.on_disconnect(lambda client: print(f"Disconnected: {client.addr}"))
```

## Client callbacks

```python
from veltix import Client, ClientConfig
from veltix import DisconnectState

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))

client.on_connect(lambda: print("Handshake complete!"))
client.on_recv(lambda response: print(response.text))
client.on_disconnect(lambda state: print(f"Disconnected — permanent={state.permanent}"))
```

## Routing vs on_recv

For per-type handling, prefer `@server.route()` / `@client.route()` over a global `on_recv`. Routes take priority and
run in the thread pool just like `on_recv`.

```python
CHAT = MessageType("chat")


@server.route(CHAT)
def on_chat(client, response):
    ...  # only called for CHAT messages


server.on_recv(fallback)  # called for everything else
```

See the [Routing guide](routing.md) for full details.

## Thread pool

All `on_recv` callbacks and route callbacks run in a dedicated thread pool (`CallbackExecutor`). This means:

- A slow or blocking callback **never** delays message reception
- Exceptions inside callbacks are caught and logged — they never crash the recv loop
- Workers are configurable via `max_workers` in `ServerConfig` / `ClientConfig`

```python
# Increase workers for slow callbacks
config = ServerConfig(host="0.0.0.0", port=8080, max_workers=8)
```

!!! warning
`on_connect` and `on_disconnect` run directly in the recv thread — keep them fast.
