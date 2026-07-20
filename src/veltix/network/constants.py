from __future__ import annotations

import struct

MAGIC = b"VX"

REQUEST_ID_SIZE = 2

HEADER_STRUCT = struct.Struct(f">2sBHI4s{REQUEST_ID_SIZE}s")

HEADER_SIZE = HEADER_STRUCT.size
