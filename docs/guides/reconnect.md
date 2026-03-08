# Auto-Reconnect

Veltix can automatically reconnect after a connection failure, both on the initial `connect()` and after a mid-session
disconnection.

## Configuration

```python
from veltix import Client, ClientConfig

client = Client(ClientConfig(
    server_addr="127.0.0.1",
    port=8080,
    retry=5,  # number of reconnection attempts (default: 0 = disabled)
    retry_delay=1.0,  # seconds between attempts (default: 1.0)
))
```

With `retry=0` (default), the client behaves exactly as in v1.4.0 — no automatic reconnection.

## DisconnectState

The client `on_disconnect` callback now receives a `DisconnectState` with full context at every event.

```python
from veltix import DisconnectState, DisconnectReason


def on_disconnect(state: DisconnectState):
    print(f"permanent:  {state.permanent}")  # True = no more retries
    print(f"attempt:    {state.attempt}")  # current attempt number
    print(f"retry_max:  {state.retry_max}")  # configured max
    print(f"reason:     {state.reason}")  # SERVER_CLOSED | ERROR | MANUAL
```

| Field       | Type               | Description                                                    |
|-------------|--------------------|----------------------------------------------------------------|
| `permanent` | `bool`             | `True` when retries are exhausted or `stop_retry()` was called |
| `attempt`   | `int`              | Current retry attempt (0 = initial disconnection)              |
| `retry_max` | `int`              | Configured maximum retry count                                 |
| `reason`    | `DisconnectReason` | `SERVER_CLOSED`, `ERROR`, or `MANUAL`                          |

## Callback behavior

`on_disconnect` fires at every step of the retry sequence:

```
server crashes
    → on_disconnect(permanent=False, attempt=0, reason=SERVER_CLOSED)  ← initial disconnect
    → [retry 1 fails]
    → on_disconnect(permanent=False, attempt=1, reason=SERVER_CLOSED)
    → [retry 2 succeeds]
    → on_connect()                                                       ← reconnected!
```

If all attempts are exhausted:

```
    → on_disconnect(permanent=True, attempt=5, reason=SERVER_CLOSED)    ← final
```

## Full example

```python
from veltix import Client, ClientConfig, Events
from veltix.client.client import DisconnectState

client = Client(ClientConfig(
    server_addr="127.0.0.1",
    port=8080,
    retry=5,
    retry_delay=1.0,
))


def on_disconnect(state: DisconnectState):
    if state.permanent:
        print(f"Permanently disconnected — reason: {state.reason.name}")
    else:
        print(f"Retrying... attempt {state.attempt}/{state.retry_max}")


client.set_callback(Events.ON_CONNECT, lambda: print("Connected!"))
client.set_callback(Events.ON_DISCONNECT, on_disconnect)
client.connect()
```

## Manual control

```python
# Cancel all pending retries — fires on_disconnect(permanent=True)
client.stop_retry()

# Force a new attempt even if retry_max was reached
client.retry()

# Force a new attempt and override retry_max
client.retry(max=10)
```

!!! warning
Callbacks and routes are preserved across reconnections — no need to re-register them.
