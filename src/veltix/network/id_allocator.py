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

    Allocates sequential IDs within a fixed range [0, max_ids).
    Wraps around to 0 after reaching max_ids. IDs currently tracked as
    pending (via the ``is_pending`` callback) are skipped so a request ID
    is never reused while a ``send_and_wait`` is still awaiting its response.
    """

    __slots__ = ("_max", "_counter", "_lock", "_is_pending")

    def __init__(
        self,
        max_ids: int = 65535,
        is_pending: Callable[[int], bool] | None = None,
    ) -> None:
        self._max = max_ids
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
            while self._is_pending(self._counter):
                self._counter = (self._counter + 1) % self._max
                if self._counter == start:
                    raise IDsExhaustedError("all IDs are currently pending")
            current = self._counter
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
