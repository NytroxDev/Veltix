"""Hello Veltix — minimal example. Run this file, it starts server + client."""

from veltix import (
    Client,
    ClientConfig,
    ClientInfo,
    MessageType,
    Request,
    Response,
    Server,
    ServerConfig,
)

HELLO = MessageType("hello")

server = Server(ServerConfig(port=8080))
client = Client(ClientConfig(port=8080))


@server.route(HELLO)
def on_server(client: ClientInfo, response: Response) -> None:
    print(f"Server got: {response.content.decode()}")
    reply = Request(HELLO, b"Hello from server!")
    reply.respond(response)
    server.send(reply, client)


@client.route(HELLO)
def on_client(response: Response) -> None:
    print(f"Client got: {response.content.decode()}")


server.start()
client.connect()

response = client.send_and_wait(Request(HELLO, b"Hello from client!"), timeout=3.0)
if response:
    print(f"Response: {response.content.decode()}")

server.close_all()
