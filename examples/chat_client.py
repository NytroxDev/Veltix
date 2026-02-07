"""
Simple Chat Client Example for Veltix

A chat client that can send and receive messages in a group chat.
"""

import threading

from Veltix import Binding, Client, ClientConfig, MessageType, Request

# Define message types (must match server)
CHAT = MessageType(code=201, name="chat", description="Chat message")
JOIN = MessageType(code=202, name="join", description="User joined")
LEAVE = MessageType(code=203, name="leave", description="User left")


def main():
    # Configure client
    config = ClientConfig(server_addr="127.0.0.1", port=9000)

    client = Client(config)
    sender = client.get_sender()

    # Callback when message received
    def on_message(response):
        message = response.content.decode("utf-8")

        # Clear current input line and print message
        print(f"\r{message}")
        print("You: ", end="", flush=True)

    # Bind callback
    client.bind(Binding.ON_RECV, on_message)

    # Connect to server
    print("Connecting to chat server...")
    if not client.connect():
        print("Failed to connect to server!")
        return

    print("Connected to chat!")
    print("Type your messages and press Enter to send")
    print("Type 'quit' to exit")
    print("-" * 50)

    try:
        while True:
            # Get user input
            message = input("You: ")

            if message.lower() == "quit":
                break

            if not message.strip():
                continue

            # Send message
            request = Request(CHAT, message.encode("utf-8"))

            if not sender.send(request):
                print("Failed to send message!")

    except KeyboardInterrupt:
        print("\nInterrupted by user")

    finally:
        print("\nDisconnecting from chat...")
        client.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    main()
