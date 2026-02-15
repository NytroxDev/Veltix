"""
Echo Client Example for Veltix

A simple client that sends messages to the echo server and prints responses.
"""

import time

from veltix import Client, ClientConfig, Events, MessageType, Request

# Define message type (must match server)
ECHO = MessageType(code=200, name="echo", description="Echo message")


def main():
    # Configure client
    config = ClientConfig(server_addr="127.0.0.1", port=8080)

    client = Client(config)
    sender = client.get_sender()

    # Callback when message received
    def on_message(response):
        echo = response.content.decode("utf-8")
        print(f"Server response: {echo}")
        print(f"Latency: {response.latency}ms")

    # Bind callback
    client.set_callback(Events.ON_RECV, on_message)

    # Connect to server
    print("Connecting to server...")
    if not client.connect():
        print("Failed to connect to server!")
        return

    print("Connected! Type messages to send (or 'quit' to exit)")
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
            request = Request(ECHO, message.encode("utf-8"))

            if sender.send(request):
                print("Message sent, waiting for echo...")
            else:
                print("Failed to send message!")

            # Give time for response
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nInterrupted by user")

    finally:
        print("\nDisconnecting...")
        client.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    main()
