# Veltix

> **The networking library you always wanted**

<!-- Uncomment after PyPI deployment
[![PyPI version](https://badge.fury.io/py/veltix.svg)](https://badge.fury.io/py/veltix)
[![Python versions](https://img.shields.io/pypi/pyversions/veltix.svg)](https://pypi.org/project/veltix/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://pepy.tech/badge/veltix)](https://pepy.tech/project/veltix)
-->

**Veltix** is a modern, simple, and powerful Python networking library built on TCP with a custom binary protocol. It's designed to be **easy enough for beginners** while **powerful enough for production** — no compromises.

---

## ✨ Why Veltix?

Existing Python networking libraries are either:
- 🔧 **Too low-level** (raw sockets, hard to use)
- 🚫 **Too limited** (can't build custom protocols)
- 🔒 **Not extensible** (hard to add features)

**Veltix solves all of this:**

- 🚀 **Simple & Intuitive API** - Write a networked app in minutes
- 🔐 **Built-in Message Integrity** - SHA256 hash verification on every message
- 📦 **Custom Binary Protocol** - Fast, lightweight, and extensible
- 🔌 **Extensible Message Types** - Create your own message types easily
- ⚡ **Multi-threaded by Default** - Handle multiple clients automatically
- 🎯 **Zero Dependencies** - Pure Python stdlib, nothing else needed

---

## 🚀 Quick Start

### Installation

```bash
pip install veltix
```

### Your First Server (30 seconds!)

```python
from veltix import Server, ServerConfig, MessageType, Request

# Define a message type
CHAT = MessageType(code=200, name="chat", description="Chat message")

# Configure server
config = ServerConfig(host="0.0.0.0", port=8080)
server = Server(config)

# Handle incoming messages
def on_message(client, response):
    print(f"[{client.addr}] {response.content.decode()}")
    
    # Echo back to client
    reply = Request(CHAT, b"Message received!")
    server.send_to(client, reply.compile())

server.bind("on_recv", on_message)
server.start()

print("Server running on port 8080...")
input("Press Enter to stop...")
server.close_all()
```

### Your First Client

```python
from veltix import Client, ClientConfig, MessageType, Request

CHAT = MessageType(code=200, name="chat")

# Configure client
config = ClientConfig(server_addr="127.0.0.1", port=8080)
client = Client(config)

# Handle server responses
def on_message(response):
    print(f"Server: {response.content.decode()}")

client.bind("on_recv", on_message)
client.connect()

# Send a message
msg = Request(CHAT, b"Hello, Server!")
client.send(msg.compile())

input("Press Enter to disconnect...")
client.disconnect()
```

**That's it!** You just built a networked client-server app. 🎉

---

## 🎯 Features

### Core Features (v1.0.0)

- ✅ **TCP Server** with automatic multi-threading (one thread per client)
- ✅ **TCP Client** with background receive thread
- ✅ **Binary Protocol** with 46-byte header (type, size, hash, timestamp)
- ✅ **Message Integrity** - SHA256 verification prevents corruption
- ✅ **Custom Message Types** - Extensible type system (0-65535 codes)
- ✅ **Latency Tracking** - Built-in `.latency` property on responses
- ✅ **Event Callbacks** - `on_recv`, `on_connect`, `on_disconnect`
- ✅ **Zero Dependencies** - Pure Python, no external packages

### Coming Soon

- 🔐 **v2.0.0** - End-to-end encryption (ChaCha20-Poly1305, X25519, Ed25519)
- ⚡ **v3.0.0** - Rust performance layer (10-100x faster)
- 🚀 **Future** - UDP support, compression, WebSockets, auto-reconnect

---

## 📖 Documentation

### Message Types

Veltix uses a type system to identify different kinds of messages:

```python
from veltix import MessageType

# User types (200-499)
CHAT = MessageType(code=200, name="chat", description="Chat messages")
FILE_TRANSFER = MessageType(code=201, name="file", description="File data")
HEARTBEAT = MessageType(code=202, name="ping", description="Keep-alive ping")

# System types (0-199) - Reserved for Veltix internal use
# Plugin types (500-65535) - Auto-assigned for plugins
```

**Type Code Ranges:**
- `0-199`: System types (reserved for Veltix internals)
- `200-499`: User types (free for your application)
- `500-65535`: Plugin types (auto-assigned)

### Binary Protocol

Every message has a **46-byte header** followed by variable-length content:

```
[Type: 2 bytes]      - Message type code (uint16)
[Size: 4 bytes]      - Content size in bytes (uint32)
[Hash: 32 bytes]     - SHA256 of content (integrity check)
[Timestamp: 8 bytes] - Milliseconds since epoch (uint64)
[Content: N bytes]   - Actual message data
```

**Why binary?**
- Fast to parse (no JSON overhead)
- Compact (efficient on network)
- Type-safe (explicit message types)
- Verified (hash prevents corruption)

### Request & Response

**Request** - Used to SEND a message:
```python
from veltix import Request, MessageType

CHAT = MessageType(code=200, name="chat")

# Create a request
msg = Request(CHAT, b"Hello, world!")

# Compile to bytes (ready to send)
data = msg.compile()

# Send it
client.send(data)
```

**Response** - Received when a message arrives:
```python
def on_message(response):
    print(f"Type: {response.type.name}")           # Message type
    print(f"Content: {response.content.decode()}") # Message data
    print(f"Timestamp: {response.timestamp}")      # When sent
    print(f"Hash: {response.hash.hex()}")          # SHA256 hash
    print(f"Latency: {response.latency}ms")        # Round-trip time
```

### Server API

```python
from veltix import Server, ServerConfig

# Configure
config = ServerConfig(
    host="0.0.0.0",         # Bind address
    port=8080,              # Port
    max_clients=100,        # Max simultaneous clients
    buffer_size=4096        # Receive buffer size
)

server = Server(config)

# Callbacks
server.bind("on_recv", lambda client, response: ...)     # Message received
server.bind("on_connect", lambda client: ...)            # Client connected
server.bind("on_disconnect", lambda client: ...)         # Client disconnected

# Control
server.start()                           # Start listening
server.send_to(client, data)             # Send to specific client
server.send_all(data)                    # Broadcast to all clients
server.close_client(client)              # Disconnect a client
server.close_all()                       # Stop server, disconnect all
```

### Client API

```python
from veltix import Client, ClientConfig

# Configure
config = ClientConfig(
    server_addr="127.0.0.1",  # Server IP
    port=8080,                # Server port
    buffer_size=4096,         # Receive buffer size
    timeout=30.0              # Connection timeout
)

client = Client(config)

# Callbacks
client.bind("on_recv", lambda response: ...)       # Message received
client.bind("on_connect", lambda: ...)             # Connected to server
client.bind("on_disconnect", lambda: ...)          # Disconnected

# Control
client.connect()                # Connect to server
client.send(data)               # Send message
client.disconnect()             # Close connection
```

---

## 💡 Examples

### Echo Server

```python
from veltix import Server, ServerConfig, MessageType, Request

ECHO = MessageType(code=200, name="echo")

server = Server(ServerConfig(port=8080))

def echo_handler(client, response):
    # Echo the message back
    reply = Request(ECHO, response.content)
    server.send_to(client, reply.compile())

server.bind("on_recv", echo_handler)
server.start()

input("Server running. Press Enter to stop...")
server.close_all()
```

### Simple Chat

```python
from veltix import Server, ServerConfig, MessageType

CHAT = MessageType(code=200, name="chat")

server = Server(ServerConfig(port=8080))

def broadcast_message(sender_client, response):
    username = sender_client.addr[0]
    message = response.content.decode()
    
    print(f"[{username}] {message}")
    
    # Broadcast to all clients except sender
    for client in server.clients:
        if client != sender_client:
            server.send_to(client, response.compile())

server.bind("on_recv", broadcast_message)
server.start()

print("Chat server running on port 8080...")
input("Press Enter to stop...")
server.close_all()
```

### File Transfer

```python
from veltix import Client, ClientConfig, MessageType, Request

FILE = MessageType(code=201, name="file")

client = Client(ClientConfig(server_addr="192.168.1.100", port=8080))

def send_file(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
    
    msg = Request(FILE, data)
    client.send(msg.compile())
    print(f"Sent {len(data)} bytes")

client.connect()
send_file("document.pdf")
client.disconnect()
```

### Latency Monitor

```python
from veltix import Client, ClientConfig, MessageType, Request
import time

PING = MessageType(code=202, name="ping")

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))

def check_latency(response):
    print(f"Latency: {response.latency}ms")

client.bind("on_recv", check_latency)
client.connect()

# Send ping every second
while True:
    ping = Request(PING, b"ping")
    client.send(ping.compile())
    time.sleep(1)
```

More examples in the [`examples/`](examples/) directory!

---

## 🏗️ Architecture

Veltix is designed with simplicity and extensibility in mind:

```
veltix/
├── server/
│   └── server.py          # Server, ServerConfig, ClientInfo
├── client/
│   └── client.py          # Client, ClientConfig
├── network/
│   ├── request.py         # Request, Response
│   ├── types.py           # MessageType, MessageTypeRegistry
│   └── sender.py          # Sender (coming soon)
├── utils/
│   ├── network.py         # Low-level send/recv helpers
│   └── binding.py         # Event binding system
└── exceptions.py          # Custom exceptions
```

**Design Principles:**
- **Simplicity First** - Easy API for common cases
- **Power When Needed** - Advanced features available
- **Zero Dependencies** - Nothing to install but Veltix
- **Type Safety** - Type hints everywhere
- **Extensible** - Build plugins and custom protocols

---

## 🔧 Advanced Usage

### Custom Message Type Registry

```python
from veltix.network.types import MessageTypeRegistry, MessageType

# Access the global registry
registry = MessageTypeRegistry()

# Register custom types
CUSTOM = MessageType(code=250, name="custom")
registry.register(CUSTOM)

# Retrieve by code
msg_type = registry.get(250)
print(msg_type.name)  # "custom"

# Check if registered
if registry.has(250):
    print("Type 250 is registered!")
```

### Error Handling

```python
from veltix import Client, ClientConfig
from veltix.exceptions import ConnectionError, MessageError

client = Client(ClientConfig(server_addr="127.0.0.1", port=8080))

try:
    client.connect()
except ConnectionError as e:
    print(f"Failed to connect: {e}")

try:
    client.send(invalid_data)
except MessageError as e:
    print(f"Invalid message: {e}")
```

### Multi-Client Server Pattern

```python
from veltix import Server, ServerConfig
import threading

server = Server(ServerConfig(port=8080))

# Track clients
clients_lock = threading.Lock()
active_clients = set()

def on_connect(client):
    with clients_lock:
        active_clients.add(client)
    print(f"Client connected: {client.addr}")

def on_disconnect(client):
    with clients_lock:
        active_clients.discard(client)
    print(f"Client disconnected: {client.addr}")

server.bind("on_connect", on_connect)
server.bind("on_disconnect", on_disconnect)
server.start()
```

---

## 🤝 Contributing

We love contributions! Whether you're:
- 🐛 Reporting bugs
- 💡 Suggesting features
- 📝 Improving documentation
- 💻 Writing code
- ⭐ Starring the repo

**Every contribution matters!**

Read our [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

**Good first issues:** Look for the `good first issue` label in [Issues](https://github.com/YOUR-USERNAME/veltix/issues).

---

## 🗺️ Roadmap

### v1.0.0 - MVP ✅ (Current)
- Core TCP server/client
- Binary protocol with integrity
- Message type system
- Documentation & examples

### v2.0.0 - Security 🔐 (Planned)
- End-to-end encryption (ChaCha20-Poly1305)
- Key exchange (X25519 ECDH)
- Digital signatures (Ed25519)
- Perfect Forward Secrecy

### v3.0.0 - Performance ⚡ (Future)
- Rust core for critical paths
- 10-100x performance improvements
- Memory optimization
- Async/await support

### v4.0.0+ - Features 🚀 (Ideas)
- UDP support with reassembly
- Compression (zstd)
- WebSocket support
- Auto-reconnection
- Plugin system
- Metrics & monitoring

---

## 📊 Benchmarks

*Benchmarks coming soon after v1.0.0 release*

---

## 📄 License

Veltix is released under the [MIT License](LICENSE).

```
MIT License

Copyright (c) 2025 Veltix Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...
```

---

## 🙏 Acknowledgments

Built with ❤️ by developers who were frustrated with existing networking libraries.

Special thanks to:
- The Python community
- All contributors and early adopters
- Everyone who stars, shares, and uses Veltix

---

## 📞 Support

- 📖 **Documentation:** [Coming soon]
- 🐛 **Bug Reports:** [GitHub Issues](https://github.com/YOUR-USERNAME/veltix/issues)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/YOUR-USERNAME/veltix/discussions)
- 🌐 **Website:** [Coming soon]

<!-- Discord badge - uncomment after v1.0 launch
[![Discord](https://img.shields.io/discord/YOUR_DISCORD_ID?color=7289da&label=Discord&logo=discord&logoColor=white)](https://discord.gg/YOUR_INVITE)
-->

---

## ⭐ Star History

<!-- Uncomment after some stars
[![Star History Chart](https://api.star-history.com/svg?repos=YOUR-USERNAME/veltix&type=Date)](https://star-history.com/#YOUR-USERNAME/veltix&Date)
-->

---

<div align="center">

**[⬆ Back to Top](#veltix)**

Made with 🔥 by the Veltix team

**If you find Veltix useful, consider giving it a star! ⭐**

</div>
