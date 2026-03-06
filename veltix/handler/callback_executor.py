"""Callback executor for Veltix — isolates callback execution from the recv loop."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..logger.core import Logger


class CallbackExecutor:
    """
    Executes callbacks in a thread pool to avoid blocking the recv loop.

    Instead of calling on_recv() directly in the receive thread, the
    RequestHandler submits the call to this executor. This ensures that
    slow or blocking callbacks (heavy computation, sleep, I/O) never
    delay message reception.

    Usage::

        executor = CallbackExecutor(max_workers=4)
        executor.submit(on_recv, client, response)
        executor.shutdown()
    """

    def __init__(self, max_workers: int = 4) -> None:
        """
        Initialize the callback executor.

        Args:
            max_workers: Maximum number of concurrent callback threads (default: 4).
                         Increase for high-concurrency workloads with slow callbacks.
        """
        self._logger = Logger.get_instance()
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

        self._logger.debug(f"CallbackExecutor initialized with {max_workers} workers")

    def submit(self, func: Callable, *args: Any) -> None:
        """
        Submit a callback for asynchronous execution.

        Returns immediately — the callback runs in a worker thread.
        Exceptions raised inside the callback are caught and logged,
        so they never propagate back to the recv loop.

        Args:
            func: Callback function to execute
            *args: Arguments to pass to the callback
        """

        def _safe_run() -> None:
            try:
                func(*args)
            except Exception as e:
                self._logger.error(f"Error in callback {func.__name__}: {type(e).__name__}: {e}")

        self._executor.submit(_safe_run)
        self._logger.trace(f"Submitted callback {func.__name__} to executor")

    def shutdown(self) -> None:
        """
        Shutdown the executor gracefully.

        Waits for all running callbacks to complete before returning.
        Should be called when the server/client is shutting down.
        """
        self._logger.debug("Shutting down CallbackExecutor...")
        self._executor.shutdown(wait=True)
        self._logger.debug("CallbackExecutor shutdown complete")
