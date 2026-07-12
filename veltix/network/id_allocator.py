"""ID allocation for the compact Veltix v2 protocol."""

from __future__ import annotations

import threading


class IDAllocator:
    """
    Thread-safe monotonic ID allocator for per-connection request IDs.

    Allocates sequential IDs within a fixed range [0, max_ids).
    Wraps around to 0 after reaching max_ids.
    """

    __slots__ = ("_max", "_counter", "_lock")

    def __init__(self, max_ids: int = 30000) -> None:
        self._max = max_ids
        self._counter = 0
        self._lock = threading.Lock()

    def allocate(self) -> int:
        """Allocate the next local ID."""
        with self._lock:
            current = self._counter
            self._counter = (self._counter + 1) % self._max
            return current

    @property
    def max_ids(self) -> int:
        """Maximum number of unique IDs before wrap-around."""
        return self._max


class ClientAllocator:
    """
    Server-side counter that assigns unique offsets to connected clients.

    Each client receives a unique offset so that
    ``wire_id + client_offset`` produces a globally unique ID across
    all connected clients.
    """

    __slots__ = ("_range_size", "_index", "_lock")

    def __init__(self, range_size: int = 30000) -> None:
        self._range_size = range_size
        self._index = 0
        self._lock = threading.Lock()

    def register(self) -> int:
        """Register a new client and return its unique index."""
        with self._lock:
            idx = self._index
            self._index += 1
            return idx

    def global_id(self, client_index: int, wire_id: int) -> int:
        """Compute globally unique ID from client index and wire ID."""
        return client_index * self._range_size + wire_id
