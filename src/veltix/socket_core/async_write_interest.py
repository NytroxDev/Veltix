"""Selector write-interest bookkeeping for the async socket backend."""

from __future__ import annotations

import contextlib
import selectors
import threading
from typing import Protocol


class WriteInterestSocket(Protocol):
    """A socket whose selector registration this registry can mirror.

    Implemented by both the async backend itself (for the client role) and
    by the connections it accepts. ``fileno`` is what the selector keys
    registrations on; ``_has_outbound`` is what decides the interest set.
    """

    def fileno(self) -> int:
        """Return the underlying file descriptor."""
        ...

    def _has_outbound(self) -> bool:
        """Return True when the socket has bytes queued for writing."""
        ...


class AsyncWriteInterest:
    """Keeps a selector's ``EVENT_WRITE`` registrations in sync with queued data.

    Senders run in arbitrary threads: they report a socket holding queued
    outbound bytes here, and the selector thread drains that report once per
    loop iteration, adding or removing ``EVENT_WRITE`` so the loop never
    spins on a busy-tick. The fast path stays O(1): no per-client work when
    nothing is queued.

    One instance per owning socket. Accepted sockets get none, they report
    through the registry of the parent that accepted them.

    Attributes:
        _selector: The selector whose registrations are mirrored.
    """

    __slots__ = ("_selector", "_state", "_dirty", "_dirty_lock", "_conn_ids", "_owner_key")

    def __init__(self, selector: selectors.BaseSelector) -> None:
        """Initialise the registry for one selector.

        Args:
            selector: The selector whose interest sets are mirrored.
        """
        self._selector = selector
        self._state: dict[int, bool] = {}
        self._dirty: list[WriteInterestSocket] = []
        self._dirty_lock = threading.Lock()
        self._conn_ids: dict[int, int] = {}
        self._owner_key: int | str | None = None

    def set_owner_key(self, key: int | str | None) -> None:
        """Set the selector data key of the owning socket itself.

        Args:
            key: The key the owner is registered under, or None when the
                owner is a listener and has nothing of its own to flush.
        """
        self._owner_key = key

    def register_conn(self, sock: WriteInterestSocket, client_id: int) -> None:
        """Record the selector data key of an accepted socket.

        Args:
            sock: The socket accepted by the owner.
            client_id: The client id it was registered under.
        """
        self._conn_ids[id(sock)] = client_id

    def forget(self, sock: WriteInterestSocket) -> None:
        """Drop every trace of a socket that is going away.

        Args:
            sock: The socket being closed.
        """
        self._state.pop(id(sock), None)
        self._conn_ids.pop(id(sock), None)

    def mark_dirty(self, sock: WriteInterestSocket) -> None:
        """Report a socket with queued outbound data and wake the selector.

        Called from whichever thread ran the send, so the fast path is a
        single list append under a lock.

        Args:
            sock: The socket that queued outbound bytes.
        """
        with self._dirty_lock:
            self._dirty.append(sock)
        # wakeup() lives on the concrete selector (e.g. EpollSelector), not on
        # BaseSelector, so resolve it dynamically.
        wakeup = getattr(self._selector, "wakeup", None)
        if wakeup is not None:
            with contextlib.suppress(OSError):
                wakeup()

    def sync_dirty(self, owner: WriteInterestSocket) -> None:
        """Register write interest for sockets that reported queued data.

        Only the selector thread calls this, once per loop iteration.

        Args:
            owner: The socket owning this registry. When it reports itself it
                is only synced if it is a client connection, a listener has
                nothing of its own to flush.
        """
        with self._dirty_lock:
            dirty = self._dirty
            self._dirty = []
        for sock in dirty:
            if sock is owner:
                if self._owner_key is not None:
                    self.sync_socket_interest(sock, self._owner_key)
                continue
            client_id = self._conn_ids.get(id(sock))
            if client_id is None:
                continue
            self.sync_socket_interest(sock, client_id)

    def sync_socket_interest(self, sock: WriteInterestSocket, data: int | str) -> None:
        """Mirror a socket's outbound state onto the selector interest set.

        Only the selector thread calls this. Sockets with queued data are
        registered for ``EVENT_WRITE``; once drained they go back to
        ``EVENT_READ`` only, so the loop never spins on a busy-tick.

        Args:
            sock: The socket to sync.
            data: Selector data key carried by the registration.
        """
        wants_write = sock._has_outbound()
        sid = id(sock)
        if self._state.get(sid) == wants_write:
            return
        with contextlib.suppress(KeyError, OSError, ValueError):
            if wants_write:
                self._selector.modify(sock, selectors.EVENT_READ | selectors.EVENT_WRITE, data=data)
            else:
                self._selector.modify(sock, selectors.EVENT_READ, data=data)
        self._state[sid] = wants_write

    def reset(self) -> None:
        """Forget every socket and pending report (owning socket closing)."""
        self._state.clear()
        self._conn_ids.clear()
        with self._dirty_lock:
            self._dirty.clear()
