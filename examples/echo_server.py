from veltix import ClientInfo, MessageType, Request, Response, Server, ServerConfig

ECHO = MessageType("echo")

server = Server(ServerConfig(port=8080))


@server.route(ECHO)
def on_echo(client: ClientInfo, response: Response) -> None:
    print(f"[{client.ip}] {response.text}")
    server.send(Request(ECHO, response.content), client)


server.on_connect(lambda c: print(f"+ {c.ip}:{c.port}"))
server.on_disconnect(lambda c: print(f"- {c.ip}:{c.port}"))

server.start()
print("Echo server running on port 8080")
server.wait_until_closed()
