from veltix.server.server import ClientInfo

# Veltix

# The networking library you always wanted

[![PyPI](https://img.shields.io/pypi/v/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![Python](https://img.shields.io/pypi/pyversions/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![License](https://img.shields.io/github/license/NytroxDev/Veltix?cacheSeconds=300)](https://github.com/NytroxDev/Veltix/blob/main/LICENSE)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/veltix?period=total&units=NONE&left_color=BLACK&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/veltix)

## ✨ Features

- 🚀 **Dead simple API** - Get started in minutes, not hours
- 🔒 **Message integrity** - Built-in SHA256 hash verification
- 📦 **Custom binary protocol** - Lightweight and efficient
- 🪶 **Zero dependencies** - Pure Python stdlib only
- 🔌 **Extensible** - Custom message types with plugin support
- ⚡ **Multi-threaded** - Handle multiple clients automatically
- 🔄 **Request/Response pattern** - Built-in send_and_wait with timeout support
- 📡 **Built-in ping/pong** - Automatic latency measurement
- 📝 **Integrated logging** - Powerful, colorful, production-ready logger
- 🛡️ **Enhanced security** - Improved error handling and data validation

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
from veltix import Server, ClientInfo, ServerConfig, Response, MessageType, Request, Events

# Define message type
CHAT = MessageType(code=200, name="chat")

# Configure server
config = ServerConfig(host="0.0.0.0", port=8080)
server = Server(config)
sender = server.get_sender()


def on_message(client: ClientInfo, response: Response):
    print(f"[{client.addr[0]}] {response.content.decode()}")
    # Broadcast to all
    reply = Request(CHAT, f"Echo: {response.content.decode()}".encode())
    sender.broadcast(reply, server.get_all_clients_sockets())


server.set_callback(Events.ON_RECV, on_message)
server.start()

input("Press Enter to stop...")
server.close_all()
```

**Client (client.py):**

```python
from veltix import Client, Response, ClientConfig, MessageType, Request, Events

CHAT = MessageType(code=200, name="chat")

config = ClientConfig(server_addr="127.0.0.1", port=8080)
client = Client(config)
sender = client.get_sender()


def on_message(response: Response):
    print(f"Server: {response.content.decode()}")


client.set_callback(Events.ON_RECV, on_message)
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

## 📝 Integrated Logger

Veltix 1.2.0 includes a powerful, production-ready logging system with colorful console output and file rotation.

### Basic Usage

```python
from veltix import Logger, LoggerConfig, LogLevel

# Get logger instance (singleton)
logger = Logger.get_instance()

# Log at different levels
logger.trace("Detailed trace information")
logger.debug("Debug information")
logger.info("General information")
logger.success("Operation successful!")
logger.warning("Warning message")
logger.error("Error occurred")
logger.critical("Critical error!")
```

### Advanced Configuration

```python
from veltix import Logger, LoggerConfig, LogLevel
from pathlib import Path

# Configure logger
config = LoggerConfig(
    level=LogLevel.DEBUG,  # Minimum log level
    enabled=True,  # Enable/disable logging
    use_colors=True,  # Colored console output
    show_timestamp=True,  # Show timestamps
    show_caller=True,  # Show file:line info
    show_level=True,  # Show level name

    # File logging
    file_path=Path("logs/veltix.log"),  # Log file path
    file_rotation_size=10 * 1024 * 1024,  # 10MB rotation
    file_backup_count=5,  # Keep 5 backup files

    # Performance
    async_write=False,  # Async file writing
    buffer_size=100,  # Buffer size for async
)

logger = Logger.get_instance(config)
```

### Logger Output Example

```
[14:23:45.123] INFO  [server.py:45] Server listening on 0.0.0.0:8080
[14:23:46.456] OK    [client.py:78] Successfully connected to server
[14:23:47.789] DEBUG [sender.py:92] Sent 156 bytes via client (request_id: a3f2...)
[14:23:48.012] WARN  [network.py:34] Connection issue occurred: ConnectionResetError
[14:23:49.345] ERROR [request.py:89] Parse error: Hash mismatch - corrupted data
```

### Log Levels

```python
from veltix import LogLevel

# Available levels (in order of severity)
LogLevel.TRACE  # Most detailed (5)
LogLevel.DEBUG  # Debug info (10)
LogLevel.INFO  # General info (20)
LogLevel.SUCCESS  # Success messages (25)
LogLevel.WARNING  # Warnings (30)
LogLevel.ERROR  # Errors (40)
LogLevel.CRITICAL  # Critical errors (50)

# Change level dynamically
logger.set_level(LogLevel.WARNING)  # Only show WARNING and above
```

### Logger Features

- **Singleton pattern** - One logger instance across your application
- **Colorful output** - Easy-to-read colored console logs
- **File rotation** - Automatic log file rotation with configurable size
- **Performance** - Optional async file writing for high-throughput apps
- **Caller info** - Automatic file:line tracking
- **Thread-safe** - Safe for multi-threaded applications
- **Zero config** - Works great out of the box with sensible defaults

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
from veltix import Server, ServerConfig, MessageType, Request, Events

ECHO = MessageType(code=201, name="echo")
server = Server(ServerConfig(host="0.0.0.0", port=8080))


def on_message(client, response):
    # Echo back with same request_id
    reply = Request(response.type, response.content, request_id=response.request_id)
    server.get_sender().send(reply, client=client.conn)


server.set_callback(Events.ON_RECV, on_message)
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
from veltix import Server, ServerConfig, Events

server = Server(ServerConfig(host="0.0.0.0", port=8080))


def on_connect(client):
    # Ping client when they connect
    latency = server.ping_client(client, timeout=2.0)
    if latency:
        print(f"Client {client.addr} latency: {latency}ms")


server.set_callback(Events.ON_CONNECT, on_connect)
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
from veltix import Server, Events

server = Server(config)

# Bind to connection event
server.set_callback(Events.ON_CONNECT, lambda client: print(f"Client connected: {client.addr}"))

# Bind to message event
server.set_callback(Events.ON_RECV, lambda client, msg: print(f"Message from {client.addr}"))
```

### Broadcasting

```python
# Broadcast to all connected clients
message = Request(CHAT, b"Server announcement!")
sender.broadcast(message, server.get_all_clients_sockets())

# Broadcast to all except specific clients
sender.broadcast(message, server.get_all_clients_sockets(), except_clients=[client1.conn])
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
| Integrated logger  | ✅      | ❌      | ⚠️      | ✅       |

## 🗺️ Roadmap

### v1.2.0 - Logging & Stability (February 2026) ✅

- Integrated powerful logging system with colors and file rotation
- Enhanced error handling throughout the codebase
- Improved sender with better broadcasting capabilities
- API improvements: `set_callback()` instead of `bind()`, `Events` enum
- Better security and data validation
- Foundation for v1.3.0 handshake system
- **Status: RELEASED**

### v1.3.0 - Handshake & Authentication (March 2026)

- Connection handshake protocol (HELLO messages)
- Client authentication system
- Server-side client validation
- Protocol version negotiation
- **Status: IN DEVELOPMENT**

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

## 🆕 What's New in 1.2.0

### Major Changes

- **🎨 Integrated Logger**: Production-ready logging with colors, file rotation, and async writing
- **🔧 API Improvements**: `set_callback()` replaces `bind()`, new `Events` enum
- **🛡️ Enhanced Security**: Better error handling and data validation throughout
- **📡 Improved Sender**: Enhanced broadcasting with exclusion lists
- **📝 Comprehensive Logging**: Detailed logs at every level for easier debugging
- **🏗️ Foundation for v1.3.0**: Prepared infrastructure for handshake system

### Breaking Changes

- `bind()` → `set_callback()`
- `Bindings` → `Events`

### Migration Guide

```python
# Old (v1.1.x)
from veltix import Bindings

server.bind(Bindings.ON_RECV, callback)

# New (v1.2.0)
from veltix import Events

server.set_callback(Events.ON_RECV, callback)
```

## 🆕 What's New in 1.2.1

### Critical Bug Fix

- **Fixed race conditions** in multi-threaded client handling
- All shared data structures now properly protected with locks

### New Features

- `ON_DISCONNECT` event for cleanup logic
- `Request.respond()` helper for easier response correlation

[See full changelog](CHANGELOG.md)

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
- **Discord:** [Join our community](https://discord.gg/NrEjSHtfMp)

---

**Built with ❤️ by Nytrox**