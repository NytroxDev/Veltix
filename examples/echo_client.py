from veltix import Client, ClientConfig, MessageType, Request

ECHO = MessageType("echo")

client = Client(ClientConfig(port=8080))


@client.route(ECHO)
def on_echo(response):
    print(f"← {response.text}")


client.connect()

while True:
    msg = input("→ ")
    if msg == "/quit":
        break
    client.send(Request(ECHO, text=msg))

client.disconnect()
