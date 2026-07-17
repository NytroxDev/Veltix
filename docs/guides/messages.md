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

### Raw bytes

```python
from veltix import Request

request = Request(CHAT, b"Hello!")
```

### Text payload

```python
request = Request(CHAT, text="Hello!")  # UTF-8 encoded automatically
```

### JSON payload

```python
request = Request(CHAT, json={"key": "value"})  # serialized to JSON automatically
```

### With custom request_id

```python
request = Request(CHAT, b"Hello!", request_id=42)  # uint16, 0–65535
```

Exactly one payload argument (`content`, `text`, or `json`) is required. Passing zero or more than one raises `RequestError`.

### Responding to a request

Use `Request.respond()` to copy the `request_id` from a received response for correlation:

```python
@server.route(ECHO)
def on_echo(client, response):
    reply = Request(ECHO, response.text)
    reply.respond(response)  # copies request_id from response
    server.send(reply, client)
```

## Response

Responses are received in callbacks. They have the following fields and properties:

```python
def on_message(client, response):
    print(response.type.name)       # message type name
    print(response.content)         # raw bytes payload
    print(response.request_id)     # int (0–65535)
```

### Content decoding

`Response` provides lazy, cached decoding helpers:

```python
def on_message(client, response):
    text = response.text          # str — UTF-8 decoded, cached
    data = response.json          # Any — parsed JSON, cached
    is_json = response.is_json    # bool — safe check, no exception
    is_text = response.is_text    # bool — safe check, no exception
```

`response.text` and `response.json` raise `InvalidContentError` if the content cannot be decoded. Use `response.is_text` and `response.is_json` for safe checks without exceptions.
