"""Buffer size presets for Veltix."""

from enum import IntEnum


class BufferSize(IntEnum):
    SMALL = 1024  # 1 KB  — low data, low memory
    MEDIUM = 8192  # 8 KB  — general purpose (default)
    LARGE = 65536  # 64 KB — frequent large messages
    HUGE = 1048576  # 1 MB  — file transfers
