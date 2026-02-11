"""
Simple Chat Server Example for Veltix

A chat server that broadcasts messages to all connected clients.
"""

from veltix import Events, MessageType, Request, Server, ServerConfig

# Define message types
CHAT = MessageType(code=201, name="chat", description="Chat message")
JOIN = MessageType(code=202, name="join", description="User joined")
LEAVE = MessageType(code=203, name="leave", description="User left")


def main():
    # Configure server
    config = ServerConfig(host="0.0.0.0", port=9000, max_connection=10)

    server = Server(config)
    sender = server.get_sender()

    # Track connected clients
    client_names = {}

    # Callback when client connects
    def on_connect(client):
        addr = f"{client.addr[0]}:{client.addr[1]}"
        client_names[client.conn] = addr

        print(f"[+] {addr} joined the chat")

        # Notify all clients
        join_msg = f"{addr} joined the chat"
        notification = Request(JOIN, join_msg.encode("utf-8"))
        sender.broadcast(notification, server.get_all_clients_sockets())

    # Callback when message received
    def on_message(client, response):
        sender_name = client_names.get(client.conn, "Unknown")
        message = response.content.decode("utf-8")

        print(f"[{sender_name}] {message}")

        # Broadcast to all clients
        chat_msg = f"[{sender_name}] {message}"
        broadcast = Request(CHAT, chat_msg.encode("utf-8"))

        sender.broadcast(broadcast, server.get_all_clients_sockets(), [client.conn])

    # Bind callbacks
    server.set_callback(Events.ON_CONNECT, on_connect)
    server.set_callback(Events.ON_RECV, on_message)

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
        sender.broadcast(notification, server.get_all_clients_sockets())

        server.close_all()
        print("Chat server stopped.")


if __name__ == "__main__":
    main()
