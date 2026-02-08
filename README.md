# Veltix

# The networking library you always wanted

[![PyPI](https://img.shields.io/pypi/v/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![Python](https://img.shields.io/pypi/pyversions/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![License](https://img.shields.io/github/license/NytroxDev/Veltix)](https://github.com/NytroxDev/Veltix/blob/main/LICENSE)

## ✨ Features

- 🚀 **Dead simple API** - Get started in minutes, not hours
- 🔒 **Message integrity** - Built-in SHA256 hash verification
- 📦 **Custom binary protocol** - Lightweight and efficient
- 🪶 **Zero dependencies** - Pure Python stdlib only
- 🔌 **Extensible** - Custom message types with plugin support
- ⚡ **Multi-threaded** - Handle multiple clients automatically
- 🔄 **Request/Response pattern** - Built-in send_and_wait with timeout support
- 📡 **Built-in ping/pong** - Automatic latency measurement

## 📖 Why Veltix?

Existing Python networking libraries are either too low-level (raw sockets) or too complex (Twisted, asyncio). Veltix
fills the gap with a simple, modern API that handles the boring parts for you.

Built by a passionate developer who wanted networking to be easy, Veltix focuses on developer experience without
sacrificing power or performance.

## 🚀 Installation

```bash
pip install veltix
```

**Requirements:** Python 3.10+

**That's it!** Zero dependencies, ready to use.

## ⚡ Quick Start

### Simple Chat Server

**Server (server.py):**

```python
from veltix import Server, ServerConfig, MessageType, Request, Binding

# Define message type
CHAT = MessageType(code=200, name="chat")

# Configure server
config = ServerConfig(host="0.0.0.0", port=8080)
server = Server(config)
sender = server.get_sender()


def on_message(client, response):
    print(f"[{client.addr[0]}] {response.content.decode()}")
    # Broadcast to all
    reply = Request(CHAT, f"Echo: {response.content.decode()}".encode())
    sender.broadcast(reply, server.get_all_clients_sockets())


server.bind(Binding.ON_RECV, on_message)
server.start()

input("Press Enter to stop...")
server.close_all()
```

**Client (client.py):**

```python
from veltix import Client, ClientConfig, MessageType, Request, Binding

CHAT = MessageType(code=200, name="chat")

config = ClientConfig(server_addr="127.0.0.1", port=8080)
client = Client(config)
sender = client.get_sender()


def on_message(response):
    print(f"Server: {response.content.decode()}")


client.bind(Binding.ON_RECV, on_message)
client.connect()

# Send message
msg = Request(CHAT, b"Hello Server!")
sender.send(msg)

input("Press Enter to disconnect...")
client.disconnect()
```

**Run:**

```bash
python server.py
python client.py  # In another terminal
```

## 🔄 Request/Response Pattern

Veltix supports synchronous request-response communication with `send_and_wait()`:

### Client Example

```python
from veltix import Client, ClientConfig, MessageType, Request

# Setup
ECHO = MessageType(code=201, name="echo")
client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))
client.connect()

# Send and wait for response
request = Request(ECHO, b"Hello Server!")
response = client.send_and_wait(request, timeout=5.0)

if response:
    print(f"Got response: {response.content.decode()}")
    print(f"Latency: {response.latency}ms")
else:
    print("Timeout or error")

client.disconnect()
```

### Server Example

```python
from veltix import Server, ServerConfig, MessageType, Request, Binding

ECHO = MessageType(code=201, name="echo")
server = Server(ServerConfig(host="0.0.0.0", port=8080))


def on_message(client, response):
    # Echo back with same request_id
    reply = Request(response.type, response.content, request_id=response.request_id)
    server.get_sender().send(reply, client=client.conn)


server.bind(Binding.ON_RECV, on_message)
server.start()

input("Press Enter to stop...")
server.close_all()
```

**Key points:**

- Use the same `request_id` in the response to match the waiting request
- The client automatically receives the response when IDs match
- Built-in timeout support to avoid infinite waiting

## 📡 Built-in Ping/Pong

Veltix includes automatic ping/pong functionality for measuring latency:

### Client to Server Ping

```python
from veltix import Client, ClientConfig

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))
client.connect()

# Ping the server
latency = client.ping_server(timeout=2.0)

if latency:
    print(f"Server latency: {latency}ms")
else:
    print("Ping timeout")

client.disconnect()
```

### Server to Client Ping

```python
from veltix import Server, ServerConfig, Binding

server = Server(ServerConfig(host="0.0.0.0", port=8080))


def on_connect(client):
    # Ping client when they connect
    latency = server.ping_client(client, timeout=2.0)
    if latency:
        print(f"Client {client.addr} latency: {latency}ms")


server.bind(Binding.ON_CONNECT, on_connect)
server.start()

input("Press Enter to stop...")
server.close_all()
```

**Features:**

- Automatic PING/PONG handling (no manual implementation needed)
- Returns latency in milliseconds
- Built-in timeout support
- Works bidirectionally (client ↔ server)

## 📦 Examples

More examples in [`examples/`](examples/):

- **Echo Server** - Simple echo implementation with send_and_wait
- **Chat Server** - Simple Chat in < 80 lines
- **Ping Example** - Latency measurement demonstrations

## 🎯 Advanced Features

### Custom Message Types

```python
from veltix import MessageType

# System messages (0-199)
PING = MessageType(0, "ping", "System ping message")

# User messages (200-499)
CHAT = MessageType(200, "chat", "Chat message")
FILE_TRANSFER = MessageType(201, "file", "File transfer")

# Plugin messages (500+)
CUSTOM_PLUGIN = MessageType(500, "plugin", "Custom plugin message")
```

### Event Callbacks

```python
from veltix import Server, Binding

server = Server(config)

# Bind to connection event
server.bind(Binding.ON_CONNECT, lambda client: print(f"Client connected: {client.addr}"))

# Bind to message event
server.bind(Binding.ON_RECV, lambda client, msg: print(f"Message from {client.addr}"))
```

### Broadcasting

```python
# Broadcast to all connected clients
message = Request(CHAT, b"Server announcement!")
sender.broadcast(message, server.get_all_clients_sockets())
```

## 📊 Comparison

| Feature            | Veltix | socket | asyncio | Twisted |
|--------------------|--------|--------|---------|---------|
| Easy API           | ✅      | ❌      | ⚠️      | ❌       |
| Zero deps          | ✅      | ✅      | ✅       | ❌       |
| Custom protocol    | ✅      | ❌      | ❌       | ⚠️      |
| Message integrity  | ✅      | ❌      | ❌       | ❌       |
| Multi-threading    | ✅      | ❌      | ❌       | ✅       |
| Request/Response   | ✅      | ❌      | ⚠️      | ✅       |
| Built-in ping/pong | ✅      | ❌      | ❌       | ❌       |

## 🗺️ Roadmap

### v1.1.0 - Request/Response (February 2026) ✅

- Request/Response pattern with send_and_wait
- Built-in ping/pong functionality
- Automatic latency measurement
- UUID-based request tracking
- **Status: RELEASED**

### v2.0.0 - Security (Summer 2026)

- End-to-end encryption (ChaCha20 + X25519 + Ed25519)
- Automatic key exchange
- Perfect forward secrecy
- **Status: PLANNED**

### v3.0.0 - Performance (Fall 2026)

- Rust core via PyO3
- 10-100x speed improvements
- Advanced optimizations
- **Status: RESEARCH**

### v4.0.0+ (2027+)

- UDP support
- Plugin ecosystem
- Compression
- WebSocket bridge

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Quick ways to help:

- ⭐ Star the project
- 🐛 Report bugs
- 📚 Improve documentation
- 💻 Submit pull requests
- 💬 Join discussions

## 🙏 Contributors

### Core Team

- **Nytrox** - Creator & Lead Developer

### Community Heroes

Thank you to everyone who has contributed through code, documentation, bug reports, and support!

Want to be listed here? Check out our [Contributing guide](CONTRIBUTING.md)!

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🔗 Links

- **Documentation:** Coming soon
- **GitHub:** [NytroxDev/Veltix](https://github.com/NytroxDev/Veltix)
- **PyPI:** [pypi.org/project/veltix](https://pypi.org/project/veltix)
- **Issues:** [Report a bug](https://github.com/NytroxDev/Veltix/issues)

---

**Built with ❤️ by Nytrox**
