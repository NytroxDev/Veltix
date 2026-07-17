# Request & Response

## Request

```python
from veltix import Request

# Raw bytes
request = Request(MY_TYPE, b"hello")

# Text payload (UTF-8 encoded automatically)
request = Request(MY_TYPE, text="hello")

# JSON payload (serialized automatically)
request = Request(MY_TYPE, json={"key": "value"})

# With explicit request_id (uint16, 0–65535)
request = Request(MY_TYPE, b"hello", request_id=42)
```

Exactly one payload argument (`content`, `text`, or `json`) is required.

### Responding to a request

Use `Request.respond()` to copy the `request_id` from a received response for correlation:

```python
@server.route(ECHO)
def on_echo(client, response):
    reply = Request(ECHO, response.text)
    reply.respond(response)  # copies request_id
    server.send(reply, client)
```

::: veltix.network.request.Request

---

## Response

```python
def on_message(client, response):
    print(response.type.name)       # message type name
    print(response.content)         # raw bytes payload
    print(response.request_id)     # int (0–65535)
```

### Content decoding

```python
response.text     # str — UTF-8 decoded, cached (raises InvalidContentError)
response.json     # Any — parsed JSON, cached (raises InvalidContentError)
response.is_json  # bool — safe check, no exception
response.is_text  # bool — safe check, no exception
```

::: veltix.network.response.Response
