"""
Echo Server Example for Veltix

A simple server that echoes back any message it receives.
"""

from veltix import ClientInfo, Events, MessageType, Request, Response, Server, ServerConfig

# Define message type
ECHO = MessageType(code=200, name="echo", description="Echo message")


def main():
    # Configure server
    config = ServerConfig(host="0.0.0.0", port=8080, max_connection=5)

    server = Server(config)
    sender = server.get_sender()

    # Callback when client connects
    def on_connect(client: ClientInfo):
        print(f"[+] Client connected: {client.addr[0]}:{client.addr[1]}")

    # Callback when message received
    def on_message(client: ClientInfo, response: Response):
        original = response.content.decode("utf-8")
        print(f"[{client.addr[0]}] Received: {original}")

        # Echo back
        echo_msg = f"Echo: {original}"
        reply = Request(ECHO, echo_msg.encode("utf-8"))

        result = sender.send(reply, client=client.conn)

        if result:
            print(f"[{client.addr[0]}] Sent: {echo_msg}")
        else:
            print(f"[{client.addr[0]}] Failed to send echo")

    # Bind callbacks
    server.set_callback(Events.ON_CONNECT, on_connect)
    server.set_callback(Events.ON_RECV, on_message)

    # Start server
    print(f"Echo server starting on {config.host}:{config.port}...")
    print("Press Ctrl+C to stop")

    server.start()

    try:
        # Keep running
        while True:
            pass
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.close_all()
        print("Server stopped.")


if __name__ == "__main__":
    main()
