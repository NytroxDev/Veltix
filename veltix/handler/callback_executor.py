"""Callback executor for Veltix."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from ..logger.core import Logger


class CallbackExecutor:
    """Executes user callbacks in a thread pool to avoid blocking the recv loop."""

    def __init__(self, max_workers: int = 4) -> None:
        self._logger = Logger.get_instance()
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit(self, func: Callable, *args: Any) -> None:
        """Submit a callback for async execution. Returns immediately."""

        def _safe_run() -> None:
            try:
                func(*args)
            except Exception as e:
                self._logger.error(f"Error in callback {func.__name__}: {type(e).__name__}: {e}")

        try:
            self._executor.submit(_safe_run)
        except RuntimeError:
            pass

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the executor, optionally waiting for in-progress callbacks."""
        self._executor.shutdown(wait=wait)
