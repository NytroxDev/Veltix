# Veltix

# The networking library you always wanted

[![PyPI](https://img.shields.io/pypi/v/veltix?cacheSeconds=300)](https://pypi.org/project/veltix/)
[![Python](https://img.shields.io/pypi/pyversions/veltix)](https://pypi.org/project/veltix/)
[![License](https://img.shields.io/github/license/NytroxDev/Veltix)](https://github.com/NytroxDev/Veltix/blob/main/LICENSE)

## ✨ Features

- 🚀 **Dead simple API** - Get started in minutes, not hours
- 🔒 **Message integrity** - Built-in SHA256 hash verification
- 📦 **Custom binary protocol** - Lightweight and efficient
- 🪶 **Zero dependencies** - Pure Python stdlib only
- 🔌 **Extensible** - Custom message types with plugin support
- ⚡ **Multi-threaded** - Handle multiple clients automatically

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

## 📦 Examples

More examples in [`examples/`](examples/):

- **Echo Server** - Simple echo implementation
- **File Transfer** - Send files over network
- **Custom Types** - Define your message types
- **Advanced Sender** - Complex messaging patterns

## 📊 Comparison

| Feature           | Veltix | socket | asyncio | Twisted |
|-------------------|--------|--------|---------|---------|
| Easy API          | ✅      | ❌      | ⚠️      | ❌       |
| Zero deps         | ✅      | ✅      | ✅       | ❌       |
| Custom protocol   | ✅      | ❌      | ❌       | ⚠️      |
| Message integrity | ✅      | ❌      | ❌       | ❌       |
| Multi-threading   | ✅      | ❌      | ❌       | ✅       |

## 🗺️ Roadmap

### v1.0.0 - Foundation (March 2026)

- Core TCP server/client
- Binary protocol with SHA256 integrity
- Custom message types
- Zero dependencies
- **Status: IN PROGRESS**

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
