# Messages

## MessageType

Every message in Veltix has a type. Types are identified by a unique integer code and a name.

### Explicit code

```python
from veltix import MessageType

CHAT = MessageType(code=200, name="chat", description="Chat message")
FILE = MessageType(code=201, name="file", description="File transfer")
```

### Auto-allocated code

Omit the code (or pass a name string as the first argument) and Veltix will automatically assign the next available code in the 200–9999 range:

```python
from veltix import MessageType

CHAT = MessageType("chat")                    # auto-allocates code 200
FILE = MessageType("file", description="...")  # auto-allocates code 201
STATUS = MessageType(name="status")            # keyword style, same result
```

!!! tip
    Auto-allocation is ideal for quick prototyping. Use explicit codes when you need stable, predictable wire values across multiple services.

### Code ranges

| Range       | Usage              |
|-------------|--------------------|
| 0–199       | System (reserved)  |
| 200–9999    | User application   |
| 10000–65535 | Plugins            |

!!! warning
    Codes 0–199 are reserved by Veltix. Use 200+ for your own message types.
    The protocol supports codes up to 65535 (uint16).

## Request

```python
from veltix import Request

# Basic request
request = Request(CHAT, b"Hello!")

# With custom request_id (for correlation)
request = Request(CHAT, b"Hello!", request_id=b"\x01\x02\x03\x04")
```

## Response

Responses are received in callbacks. They have the same fields as requests.

```python
def on_message(client, response):
    print(response.type.name)     # message type name
    print(response.content)       # raw bytes payload
    print(response.request_id)    # 4-byte request id
```
