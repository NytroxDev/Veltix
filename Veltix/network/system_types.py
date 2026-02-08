from .types import MessageType

PING = MessageType(0, "ping", "type de message pour ping le server ou un client.")
PONG = MessageType(1, "pong", "type de message pour repondre a un ping.")
