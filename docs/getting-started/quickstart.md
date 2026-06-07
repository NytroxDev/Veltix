# Quick Start

## Basic echo server

**Server:**

```python
from veltix import Server, ServerConfig, Events, MessageType, Request

ECHO = MessageType(code=200, name="echo")

server = Server(ServerConfig(host="0.0.0.0", port=8080))

def on_message(client, response):
    reply = Request(ECHO, response.content, request_id=response.request_id)
    server.get_sender().send(reply, client=client.conn)

server.set_callback(Events.ON_RECV, on_message)
server.start()

input("Press Enter to stop...")
server.close_all()
```

**Client:**

```python
from veltix import Client, ClientConfig, Events, MessageType, Request

ECHO = MessageType(code=200, name="echo")

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))
client.set_callback(Events.ON_RECV, lambda r: print(r.content.decode()))
client.connect()  # blocks until handshake is complete

client.get_sender().send(Request(ECHO, b"Hello!"))

input("Press Enter to disconnect...")
client.disconnect()
```

## Send and wait

```python
request = Request(ECHO, b"Hello!")
response = client.send_and_wait(request, timeout=5.0)

if response:
    print(f"Got: {response.content.decode()}")
else:
    print("Timeout")
```

## Ping

```python
latency = client.ping_server(timeout=2.0)
print(f"Latency: {latency}ms")
```
