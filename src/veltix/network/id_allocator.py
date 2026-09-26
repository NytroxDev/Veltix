"""ID allocation for the compact Veltix v2 protocol."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from ..exceptions import IDsExhaustedError

if TYPE_CHECKING:
    from collections.abc import Callable


class IDAllocator:
    """
    Thread-safe monotonic ID allocator for per-connection request IDs.

    Allocates sequential IDs within a fixed range [offset, offset + max_ids).
    Wraps around to *offset* after reaching the end of the range. IDs
    currently tracked as pending (via the ``is_pending`` callback) are
    skipped so a request ID is never reused while a ``send_and_wait`` is
    still awaiting its response.

    The ``offset`` lets each role reserve a disjoint slice of the wire ID
    space: clients use [0, 32768) and servers [32768, 65536), so an
    auto-assigned ID from one direction can never be mistaken for a response
    to a pending request of the other direction.
    """

    __slots__ = ("_max", "_offset", "_counter", "_lock", "_is_pending")

    def __init__(
        self,
        max_ids: int = 65535,
        offset: int = 0,
        is_pending: Callable[[int], bool] | None = None,
    ) -> None:
        self._max = max_ids
        self._offset = offset
        self._counter = 0
        self._lock = threading.Lock()
        self._is_pending = is_pending or (lambda _: False)

    def allocate(self) -> int:
        """Allocate the next available local ID, skipping pending IDs.

        Returns:
            The next available request ID.

        Raises:
            IDsExhaustedError: If every ID in the window is currently pending.
        """
        with self._lock:
            start = self._counter
            while self._is_pending(self._offset + self._counter):
                self._counter = (self._counter + 1) % self._max
                if self._counter == start:
                    raise IDsExhaustedError("all IDs are currently pending")
            current = self._offset + self._counter
            self._counter = (self._counter + 1) % self._max
            return current

    @property
    def max_ids(self) -> int:
        """Maximum number of unique IDs before wrap-around."""
        return self._max

    @max_ids.setter
    def max_ids(self, value: int) -> None:
        """Set the maximum number of unique IDs.

        Args:
            value: The new maximum number of IDs.
        """
        with self._lock:
            self._max = value
