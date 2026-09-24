"""Callback executor for Veltix."""

from __future__ import annotations

import contextlib
import threading
from queue import Empty, SimpleQueue
from typing import TYPE_CHECKING, Any

from ..internal.events import ErrorEvent

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..internal.bus import VeltixBus


class CallbackExecutor:
    """Executes user callbacks in a thread pool to avoid blocking the recv loop.

    Worker threads are daemon threads, so they never block interpreter shutdown.
    As a consequence, callbacks that are still queued or in progress when the
    process exits are dropped unless :meth:`shutdown` with ``wait=True`` is
    called beforehand.
    """

    def __init__(self, max_workers: int = 4, bus: VeltixBus | None = None) -> None:
        self.bus = bus
        self._max_workers = max_workers
        self._workers: list[threading.Thread] = []
        self._queue: SimpleQueue[Callable[[], None]] = SimpleQueue()
        self._stopped = threading.Event()
        self._spawn_workers()

    def _spawn_workers(self) -> None:
        for _ in range(self._max_workers):
            thread = threading.Thread(target=self._worker_loop, daemon=True)
            thread.start()
            self._workers.append(thread)

    def _worker_loop(self) -> None:
        while not self._stopped.is_set():
            try:
                item = self._queue.get(timeout=1.0)
            except Empty:
                continue
            with contextlib.suppress(Exception):
                item()

    def submit(self, func: Callable, *args: Any) -> None:
        """
        Submit a callback for async execution.

        Returns immediately without waiting for the callback to run. Exceptions
        raised inside the callback are caught and reported via the bus.

        Args:
            func: Callable to execute.
            *args: Positional arguments passed to the callable.
        """

        if self._stopped.is_set():
            return

        def _safe_run() -> None:
            try:
                func(*args)
            except Exception as e:
                if self.bus:
                    self.bus.emit(ErrorEvent.CALLBACK, {"error": str(e), "func": func.__name__})
                    self.bus.error(f"Error in callback {func.__name__}: {type(e).__name__}: {e}")

        self._queue.put(_safe_run)

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the executor.

        Args:
            wait: If True, blocks until all pending callbacks have run and every
                worker thread has exited.
        """
        self._stopped.set()

        if wait:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()()
                except Empty:
                    break
            for worker in self._workers:
                worker.join()
