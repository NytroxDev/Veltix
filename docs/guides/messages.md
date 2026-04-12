# Messages

## MessageType

Every message in Veltix has a type. Types are identified by a unique integer code and a name.

```python
from veltix import MessageType

CHAT = MessageType(code=200, name="chat", description="Chat message")
FILE = MessageType(code=201, name="file", description="File transfer")
```

### Code ranges

| Range    | Usage              |
|----------|--------------------|
| 0–9      | Reserved (system)  |
| 10–199   | System messages    |
| 200–499  | Application        |
| 500+     | Plugins            |

!!! warning
    Codes 0–199 are reserved by Veltix. Use 200+ for your own message types.

## Request

```python
from veltix import Request

# Basic request
request = Request(CHAT, b"Hello!")

# With custom request_id (for correlation)
request = Request(CHAT, b"Hello!", request_id=b"\x01\x02\x03\x04")
```

## Response

Responses are received in callbacks. They have the same fields as requests plus `latency`.

```python
def on_message(client, response):
    print(response.type.name)     # message type name
    print(response.content)       # raw bytes payload
    print(response.request_id)    # 4-byte request id
    print(response.latency)       # round-trip time in ms
```
