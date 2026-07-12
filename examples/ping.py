"""Ping example — measures round-trip latency between client and server."""

from veltix import Client, ClientConfig, Server, ServerConfig

server = Server(ServerConfig(port=8080))
client = Client(ClientConfig(port=8080))

server.start()
client.connect()

# Client → Server
latency = client.ping_server(timeout=3.0)
print(f"Client ping: {latency:.2f}ms" if latency else "Client ping: timeout")

# Server → Client
latency = server.ping_client(server.clients[0], timeout=3.0)
print(f"Server ping: {latency:.2f}ms" if latency else "Server ping: timeout")

server.close_all()
