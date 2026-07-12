"""
Simple Chat Server Example for Veltix

A chat server that broadcasts messages to all connected clients.
"""

from veltix import ClientInfo, MessageType, Request, Response, Server, ServerConfig

# Define message types
CHAT = MessageType("chat", description="Chat message")
JOIN = MessageType("join", description="User joined")
LEAVE = MessageType("leave", description="User left")


def main():
    # Configure server
    config = ServerConfig(host="0.0.0.0", port=9000, max_connection=10)

    server = Server(config)
    sender = server.sender

    # Track connected clients
    client_names = {}

    # Callback when client connects
    def on_connect(client: ClientInfo):
        addr = f"{client.ip}:{client.port}"
        client_names[client.conn] = addr

        print(f"[+] {addr} joined the chat")

        # Notify all clients
        join_msg = f"{addr} joined the chat"
        notification_join = Request(JOIN, join_msg.encode("utf-8"))
        sender.broadcast(notification_join)

    # Callback when message received
    def on_message(client: ClientInfo, response: Response):
        sender_name = client_names.get(client.conn, "Unknown")
        message = response.content.decode("utf-8")

        print(f"[{sender_name}] {message}")

        # Broadcast to all clients
        chat_msg = f"[{sender_name}] {message}"
        broadcast = Request(CHAT, chat_msg.encode("utf-8"))

        sender.broadcast(broadcast, except_clients=[client])

    # Bind callbacks
    server.on_connect(on_connect)
    server.on_recv(on_message)

    # Start server
    print(f"Chat server starting on port {config.port}...")
    print(f"Max connections: {config.max_connection}")
    print("Press Ctrl+C to stop")
    print("-" * 50)

    server.start()

    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\n" + "-" * 50)
        print("Shutting down chat server...")

        # Notify clients
        leave_msg = "Server is shutting down"
        notification = Request(LEAVE, leave_msg.encode("utf-8"))
        sender.broadcast(notification)

        server.close_all()
        print("Chat server stopped.")


if __name__ == "__main__":
    main()
