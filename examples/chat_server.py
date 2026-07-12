from veltix import ClientInfo, MessageType, Request, Response, Server, ServerConfig

CHAT = MessageType("chat")
JOIN = MessageType("join")
LEAVE = MessageType("leave")

server = Server(ServerConfig(port=9000))


@server.route(CHAT)
def on_chat(client: ClientInfo, response: Response) -> None:
    name = client.get_tag("name") or client.ip
    msg = f"[{name}] {response.content.decode()}"
    print(msg)
    server.broadcast(Request(CHAT, msg.encode()), except_clients=[client])


@server.route(JOIN)
def on_join(client: ClientInfo, response: Response) -> None:
    name = response.content.decode()
    client.add_tag("name", name)
    print(f"+ {name} joined")
    server.broadcast(Request(JOIN, f"{name} joined".encode()), except_clients=[client])


@server.route(LEAVE)
def on_leave(client: ClientInfo, response: Response) -> None:
    name = client.get_tag("name") or client.ip
    print(f"- {name} left")


server.on_disconnect(lambda c: print(f"- {c.get_tag('name') or c.ip} disconnected"))

server.start()
print("Chat server running on port 9000")
server.wait_until_closed()
