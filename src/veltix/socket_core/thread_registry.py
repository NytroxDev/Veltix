"""Worker-thread registry for the threading socket backend."""

from __future__ import annotations

import threading


class ThreadRegistry:
    """Tracks the worker threads owned by a threading socket.

    Holds the accept thread, the client-side receive handler and the
    per-client receive threads, plus the locks that guard them. The socket
    keeps its orchestration; this only owns the thread bookkeeping.

    Attributes:
        threads: Live per-client receive threads, keyed by thread id.
        start_th: The accept loop thread, once the socket is bound.
        thread_handler: The client-side receive thread, once connected.
    """

    __slots__ = ("threads", "start_th", "thread_handler", "_lock", "_n", "_n_lock")

    def __init__(self) -> None:
        self.threads: dict[int, threading.Thread] = {}
        self.start_th: threading.Thread | None = None
        self.thread_handler: threading.Thread | None = None
        self._lock = threading.Lock()
        self._n = 0
        self._n_lock = threading.Lock()

    def next_id(self) -> int:
        """Allocate the next client thread id (1-based).

        Returns:
            A fresh thread id, never reused for the lifetime of the socket.
        """
        with self._n_lock:
            self._n += 1
            return self._n

    def register(self, thread_id: int, thread: threading.Thread) -> None:
        """Record a started per-client receive thread.

        Args:
            thread_id: The id allocated by :meth:`next_id`.
            thread: The started thread handling that client.
        """
        with self._lock:
            self.threads[thread_id] = thread

    def pop_and_join(self, thread_id: int, timeout: float) -> None:
        """Forget a per-client receive thread and join it.

        The join happens under the lock, as it did when the socket owned the
        mapping, so a client thread cannot re-register mid-teardown.

        Args:
            thread_id: The id the thread was registered under.
            timeout: Maximum time to wait for the thread, in seconds.
        """
        with self._lock:
            thread = self.threads.pop(thread_id, None)
            self._join_foreign(thread, timeout)

    def snapshot(self) -> list[threading.Thread]:
        """Return the tracked per-client receive threads.

        Returns:
            A new list, safe to iterate while threads come and go.
        """
        with self._lock:
            return list(self.threads.values())

    def clear(self) -> None:
        """Forget every tracked per-client receive thread."""
        with self._lock:
            self.threads.clear()

    def join_foreign(self, thread: threading.Thread | None, timeout: float) -> None:
        """Join a thread unless it is the caller.

        Joining the calling thread raises, so teardown reached from inside a
        tracked thread must skip it.

        Args:
            thread: The thread to join, or None when it was never started.
            timeout: Maximum time to wait, in seconds.
        """
        self._join_foreign(thread, timeout)

    @staticmethod
    def _join_foreign(thread: threading.Thread | None, timeout: float) -> None:
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
