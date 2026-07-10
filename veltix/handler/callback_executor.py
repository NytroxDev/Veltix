"""Callback executor for Veltix."""

from __future__ import annotations

import contextlib
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Callable

from ..internal.events import ErrorEvent

if TYPE_CHECKING:
    from ..internal.bus import VeltixBus


class CallbackExecutor:
    """Executes user callbacks in a thread pool to avoid blocking the recv loop."""

    def __init__(self, max_workers: int = 4, bus: Optional[VeltixBus] = None) -> None:
        self.bus = bus
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit(self, func: Callable, *args: Any) -> None:
        """Submit a callback for async execution. Returns immediately."""

        def _safe_run() -> None:
            try:
                func(*args)
            except Exception as e:
                if self.bus:
                    self.bus.emit(ErrorEvent.CALLBACK, {"error": str(e), "func": func.__name__})
                    self.bus.error(f"Error in callback {func.__name__}: {type(e).__name__}: {e}")

        with contextlib.suppress(RuntimeError):
            self._executor.submit(_safe_run)

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the executor, optionally waiting for in-progress callbacks."""
        self._executor.shutdown(wait=wait)
