from __future__ import annotations

import struct

MAGIC = b"VX"

REQUEST_ID_SIZE = 2

# ── Header layout (15 bytes, big-endian) ──────────────────────────────────
# Offset  Size  Field         Struct format
# 0       2     MAGIC         "2s"
# 2       1     flags         "B"
# 3       2     type code     "H"
# 5       4     content size  "I"
# 9       4     CRC32 hash    "4s"
# 13      2     request id    "2s"
MAGIC_OFFSET = 0
FLAGS_OFFSET = len(MAGIC)
CODE_OFFSET = FLAGS_OFFSET + 1
SIZE_OFFSET = CODE_OFFSET + 2
HASH_OFFSET = SIZE_OFFSET + 4
REQUEST_ID_OFFSET = HASH_OFFSET + 4

HEADER_STRUCT = struct.Struct(f">2sBHI4s{REQUEST_ID_SIZE}s")

HEADER_SIZE = HEADER_STRUCT.size

# Reads MAGIC + content size from the start of a frame without unpacking the
# full header. The size field sits at SIZE_OFFSET, right after MAGIC + flags
# + code. Deriving the skip from the named offsets keeps this in sync with
# HEADER_STRUCT above.
SIZE_PREFIX_STRUCT = struct.Struct(f">2s{SIZE_OFFSET - len(MAGIC)}xI")
