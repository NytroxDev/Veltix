# Client Guide

## Configuration

```python
from veltix import Client, ClientConfig

config = ClientConfig(
    server_addr="127.0.0.1",  # Server address
    port=8080,                 # Server port
    buffer_size=1024,          # Receive buffer size in bytes
    max_message_size=10 * 1024 * 1024,  # 10MB max message size
    handshake_timeout=5.0,     # Handshake timeout in seconds
    max_workers=4,             # Thread pool size for callbacks
)

client = Client(config)
```

## Connecting

```python
success = client.connect()
```

!!! note
    `connect()` blocks until the handshake is complete. It is always safe to send messages immediately after it returns `True`.

## Callbacks

```python
from veltix import Events

client.set_callback(Events.ON_CONNECT, lambda: print("Connected!"))
client.set_callback(Events.ON_RECV, lambda response: print(response.content.decode()))
client.set_callback(Events.ON_DISCONNECT, lambda: print("Disconnected"))
```

## Sending messages

```python
client.get_sender().send(request)
```

## Send and wait

```python
response = client.send_and_wait(request, timeout=5.0)

if response:
    print(f"Got: {response.content.decode()} in {response.latency:.2f}ms")
else:
    print("Timeout")
```

## Ping

```python
latency = client.ping_server(timeout=2.0)
```

## Disconnecting

```python
client.disconnect()
```
