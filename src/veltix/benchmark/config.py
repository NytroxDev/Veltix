"""
config.py
---------
All benchmark-wide constants:
  - Terminal width
  - Message types used in simulations
  - Port assignments (one per benchmark, no collisions)
"""

from __future__ import annotations

from veltix import MessageType

# Terminal
WIDTH: int = 72

# Message types
PLAYER_MOVE = MessageType(401, "player_move")  # 32 B - position + rotation
PLAYER_SHOOT = MessageType(402, "player_shoot")  # 16 B - bullet event
GAME_STATE = MessageType(403, "game_state")  # 512 B - world snapshot
PLAYER_JOIN = MessageType(404, "player_join")  # 64 B - join handshake
CHAT_MSG = MessageType(405, "chat_msg")  # 128 B - chat packet

# Ports (one per benchmark, never reused)
PORT_MEMORY = 20_001
PORT_LATENCY = 20_002
PORT_FPS_1 = 20_003
PORT_FPS_2 = 20_006
PORT_BURST = 20_004
PORT_STRESS = 20_005
