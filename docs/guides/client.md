# Client Guide

## Configuration

```python
from veltix import Client, ClientConfig, BufferSize

config = ClientConfig(
    server_addr="127.0.0.1",  # Server address
    port=8080,  # Server port
    buffer_size=BufferSize.SMALL,  # Receive buffer size (default: 1KB)
    max_message_size=10 * 1024 * 1024,  # 10MB max message size
    handshake_timeout=5.0,  # Handshake timeout in seconds
    max_workers=4,  # Thread pool size for callbacks
    retry=0,  # Reconnection attempts (0 = disabled)
    retry_delay=1.0,  # Seconds between attempts
)

client = Client(config)
```

## Connecting

```python
success = client.connect()
```

!!! note
`connect()` blocks until the handshake is complete. It is always safe to send messages immediately after it returns
`True`.

## Routing

Use `@client.route()` to handle specific message types directly. Routes take priority over `on_recv` and run in the
thread pool.

```python
from veltix import MessageType

CHAT = MessageType(code=200, name="chat")


@client.route(CHAT)
def on_chat(response, client=None):
    print(f"Server: {response.content.decode()}")
```

Routes can also be registered and removed programmatically:

```python
client.request_handler.register_route(CHAT, on_chat)
client.request_handler.unregister_route(CHAT)
```

## Callbacks

```python
from veltix import Events, DisconnectState

client.set_callback(Events.ON_CONNECT, lambda: print("Connected!"))
client.set_callback(Events.ON_RECV, lambda response: print(response.content.decode()))
client.set_callback(Events.ON_DISCONNECT, lambda state: print(f"Disconnected — permanent={state.permanent}"))
```

!!! tip
Use `@client.route()` for per-type handlers. `on_recv` is the fallback for unrouted messages.

## Sending messages

```python
client.sender.send(request)
```

## Send and wait

```python
response = client.send_and_wait(request, timeout=5.0)

if response:
    print(f"Got: {response.content.decode()}")
else:
    print("Timeout")
```

## Ping

```python
latency = client.ping_server(timeout=2.0)
```

## Auto-reconnect

```python
client = Client(ClientConfig(
    server_addr="127.0.0.1",
    port=8080,
    retry=5,  # number of reconnection attempts
    retry_delay=1.0  # seconds between attempts
))

# Cancel retries at any time
client.stop_retry()

# Force a new attempt, optionally overriding retry_max
client.retry(max_=10)
```

See the [Auto-Reconnect guide](reconnect.md) for full details.

## Disconnecting

```python
client.disconnect()
```