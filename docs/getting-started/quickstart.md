# Quick Start

## Basic echo server

**Server:**

```python
from veltix import Server, ServerConfig, MessageType, Request, ClientInfo, Response

ECHO = MessageType("echo")

server = Server(ServerConfig(host="0.0.0.0", port=8080))


@server.route(ECHO)
def on_echo(client: ClientInfo, response: Response) -> None:
    server.send(Request(ECHO, response.content), client)


server.start()

input("Press Enter to stop...")
server.close_all()
```

**Client:**

```python
from veltix import Client, ClientConfig, MessageType, Request, Response

ECHO = MessageType("echo")

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))


@client.route(ECHO)
def on_echo(response: Response) -> None:
    print(response.text)


client.connect()  # blocks until handshake is complete

client.send(Request(ECHO, text="Hello!"))

input("Press Enter to disconnect...")
client.disconnect()
```

## Send and wait

```python
request = Request(ECHO, text="Hello!")
response = client.send_and_wait(request, timeout=5.0)

if response:
    print(f"Got: {response.text}")
else:
    print("Timeout")
```

## Ping

```python
latency = client.ping_server(timeout=2.0)
print(f"Latency: {latency}ms")
```
