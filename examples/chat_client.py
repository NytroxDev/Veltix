import sys

from veltix import Client, ClientConfig, MessageType, Request

CHAT = MessageType("chat")
JOIN = MessageType("join")
LEAVE = MessageType("leave")

name = input("Your name: ") or "anonymous"

client = Client(ClientConfig(port=9000))


@client.route(CHAT)
def on_chat(response):
    print(f"\r{response.text}")


@client.route(JOIN)
def on_join(response):
    print(f"\r⚡ {response.text}")


@client.route(LEAVE)
def on_leave(response):
    print(f"\r⚡ {response.text}")


if not client.connect():
    print("Failed to connect")
    sys.exit(1)

client.send(Request(JOIN, text=name))

try:
    while True:
        msg = input()
        if msg == "/quit":
            break
        if msg.strip():
            client.send(Request(CHAT, text=msg))
except KeyboardInterrupt:
    pass

client.send(Request(LEAVE, content=b""))
client.disconnect()
