# Callbacks & Events

## Available events

| Event             | Server signature                                     | Client signature                     |
| ----------------- | ---------------------------------------------------- | ------------------------------------ |
| `ON_CONNECT`      | `callback(client: ClientInfo)`                       | `callback()`                         |
| `ON_RECV`         | `callback(client: ClientInfo, response: Response)`   | `callback(response: Response)`       |
| `ON_DISCONNECT`   | `callback(client: ClientInfo)`                       | `callback(state: DisconnectState)`   |

!!! note
    Client `ON_DISCONNECT` now receives a [`DisconnectState`](reconnect.md) argument as of v1.5.0.

## Server callbacks

```python
from veltix import Server, ServerConfig

server = Server(ServerConfig(host="0.0.0.0", port=8080))

server.on_connect(lambda client: print(f"Connected: {client.ip}:{client.port}"))
server.on_recv(lambda client, msg: print(msg.text))
server.on_disconnect(lambda client: print(f"Disconnected: {client.ip}:{client.port}"))
```

## Client callbacks

```python
from veltix import Client, ClientConfig
from veltix import DisconnectState

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))

client.on_connect(lambda: print("Handshake complete!"))
client.on_recv(lambda response: print(response.text))
client.on_disconnect(lambda state: print(f"Disconnected - permanent={state.permanent}"))
```

## Event bus

Beyond the callbacks above, every `Server` and every `Client` owns a structured event bus
(`server.bus` / `client.bus`), powered by [Avyra](https://github.com/NytroxDev/Avyra). It carries the
lifecycle events you already know plus message, protocol, error and reconnect events that have no
callback equivalent.

Subscribers always receive two arguments: `event` and `payload`.

```python
from veltix import ClientInfo, Server, ServerConfig
from veltix.internal.events import ServerEvent

server = Server(ServerConfig(host="0.0.0.0", port=8080))


def on_join(event: ServerEvent, client: ClientInfo) -> None:
    print(f"{client.addr} joined")


server.bus.subscribe(ServerEvent.ON_CONNECT, on_join)
server.start()
```

Passing an enum class subscribes one function to every member of that family:

```python
from veltix.internal.events import ReconnectEvent

client.bus.subscribe(ReconnectEvent, lambda event, payload: print(event.name, payload))
```

`subscribe()` raises `ValueError` when the same function is already subscribed to that event;
`unsubscribe()` removes it:

```python
server.bus.unsubscribe(ServerEvent.ON_CONNECT, on_join)
```

!!! warning
    Subscribers run **synchronously in the thread that emits the event** (the accept or selector thread for
    lifecycle and protocol events), not in the `CallbackExecutor` pool. Keep them short and never block: do the
    heavy work in a route, in `on_recv`, or in your own thread.

### Bus logging

`VeltixBus` exposes the logging helpers used internally: `bus.trace()`, `debug()`, `info()`, `success()`,
`warning()`, `error()` and `critical()`, with stdlib `logging`-style `%s` formatting. The singleton
`Logger` is subscribed to every `LogEvent`, so a bus call produces normal log output:

```python
server.bus.info("client %s sent %d messages", client.addr, count)
```

### Event reference

**Server lifecycle**

| Event                         | Payload                                                                   |
| --------------------------    | ------------------------------------------------------------------------- |
| `ServerEvent.ON_CONNECT`      | `ClientInfo` (handshake already complete)                                 |
| `ServerEvent.ON_DISCONNECT`   | `ClientInfo`                                                              |
| `ServerEvent.STARTED`         | `{"host": str, "port": int}`                                              |
| `ServerEvent.STOPPED`         | `{"host": str, "port": int}`                                              |
| `ServerEvent.CLIENT_REJECTED` | `{"addr", "current", "max_client", "reason"}`                             |

**Client lifecycle**

| Event                             | Payload                                                      |
| --------------------------------  | ------------------------------------------------------------ |
| `ClientEvent.ON_CONNECT`          | `None`                                                       |
| `ClientEvent.ON_DISCONNECT`       | `DisconnectState`                                            |
| `ClientEvent.SOCKET_DISCONNECTED` | `None`                                                       |
| `ClientEvent.CONNECTING`          | `{"host": str, "port": int}`                                 |
| `ClientEvent.DISCONNECTING`       | `None`                                                       |
| `ClientEvent.TAG_ADDED`           | `{"client": (host, port), "tag": str, "value": Any}`         |
| `ClientEvent.TAG_UPDATED`         | `{"client": (host, port), "tag": str, "value": Any}`         |
| `ClientEvent.TAG_REMOVED`         | `{"client": (host, port), "tag": str}`                       |
| `ClientEvent.TAG_CLEARED`         | `{"client": (host, port)}`                                   |

`TAG_UPDATED` is emitted by `set_tag()` (create or overwrite), `TAG_ADDED` by `add_tag()` (create only).

**Message flow**

| Event                             | Payload                                                              |
| --------------------------------  | ----------------------------------------------------------------     |
| `MessageEvent.RECEIVED`           | `{"type", "length", "client"?}`                                      |
| `MessageEvent.SENT`               | `{"type", "length", "mode", "broadcast"?}`                           |
| `MessageEvent.ROUTED`             | `{"type", "route", "source"}` (`route` is `registered` or `on_recv`) |
| `MessageEvent.UNHANDLED`          | `{"type", "length", "source"}`                                       |
| `MessageEvent.PENDING_REGISTERED` | `{"request_id"}`                                                     |
| `MessageEvent.PENDING_SATISFIED`  | `{"request_id"}`                                                     |
| `MessageEvent.PENDING_TIMEOUT`    | `{"request_id", "timeout"}`                                          |
| `MessageEvent.ROUTE_REGISTERED`   | `{"type", "name"}`                                                   |
| `MessageEvent.ROUTE_UNREGISTERED` | `{"type", "name"}`                                                   |

**Protocol and errors**

| Event                              | Payload                                            |
| ---------------------------------- | -------------------------------------------------- |
| `ProtocolEvent.PING`               | `{"request_id", "from"}`                           |
| `ProtocolEvent.PONG`               | `{"request_id"}`                                   |
| `ProtocolEvent.HANDSHAKE_START`    | `{"role": "server" or "client"}`                   |
| `ProtocolEvent.HANDSHAKE_DONE`     | `{"role", "peer_version"}`                         |
| `ProtocolEvent.HANDSHAKE_FAIL`     | `{"role", "reason"}`                               |
| `ErrorEvent.NETWORK`               | `{"error", "host", "port"}`                        |
| `ErrorEvent.HANDLER`               | `{"error", "source"}`                              |
| `ErrorEvent.CALLBACK`              | `{"error", "func"}`                                |
| `ErrorEvent.SEND`                  | `{"error"}` (+ `"mode"` on sender failures)        |
| `ErrorEvent.ACCEPT`                | `{"error"}`                                        |
| `ErrorEvent.CONNECTION_REFUSED`    | `{"addr", "current", "max_client"}`                |

**Reconnect**

| Event                         | Payload                              |
| ----------------------------- | ------------------------------------ |
| `ReconnectEvent.ATTEMPT`      | `{"attempt", "max_retry"}`           |
| `ReconnectEvent.FAIL`         | `{"attempt"}`                        |
| `ReconnectEvent.SUCCESS`      | `{"attempt"}`                        |
| `ReconnectEvent.CANCELLED`    | `{"attempt"}`                        |

**Logging**

`LogEvent.TRACE`, `DEBUG`, `INFO`, `SUCCESS`, `WARNING`, `ERROR` and `CRITICAL` carry the formatted
message as a `str`. They are already wired to `Logger`; subscribe only if you need to forward them
somewhere else.

The full enum definitions live in `veltix.internal.events`.

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
- Exceptions inside callbacks are caught and logged - they never crash the recv loop
- Workers are configurable via `max_workers` in `ServerConfig` / `ClientConfig`

```python
# Increase workers for slow callbacks
config = ServerConfig(host="0.0.0.0", port=8080, max_workers=8)
```

!!! warning
    `on_connect` and `on_disconnect` run directly in the recv thread - keep them fast.
