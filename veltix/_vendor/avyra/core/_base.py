from __future__ import annotations

import threading
from enum import Enum
from typing import Awaitable, Callable, Optional, Union

Subscriber = Union[
    Callable[[Enum, Optional[object]], None],
    Callable[[Enum, Optional[object]], Awaitable[None]],
]


def _iter_members(event_type):
    """Resolve an Enum member, an Enum class, or a list into a list of members."""
    if isinstance(event_type, Enum):
        return [event_type]
    if isinstance(event_type, type) and issubclass(event_type, Enum):
        return list(event_type)
    if isinstance(event_type, list):
        return event_type
    raise TypeError(
        f"Expected an Enum member or an Enum class, got {type(event_type).__name__}"
    )


def _original_sub(func):
    """Return the original function wrapped by *func*, or *func* itself."""
    return getattr(func, "_original", func)


class _BaseEventBus:
    """Shared subscriber management for sync and async event buses."""

    def __init__(self) -> None:
        """Create an event bus.

        The bus starts empty — use :meth:`register` to add event types.
        """
        self._subscribers = {}  # type: dict[Enum, list[Subscriber]]
        self._sub_lock = threading.RLock()

    def _get_sub(self, event_type):
        """Return a lock-safe shallow copy of the subscriber list."""
        with self._sub_lock:
            lst = self._subscribers.get(event_type, None)
            return list(lst) if lst is not None else None

    def register(self, event_types):
        """Register additional event types after creation.

        Already-registered members are silently skipped.

        Args:
            event_types: An ``Enum`` member, an ``Enum`` class, or a list
                of ``Enum`` members.
        """
        with self._sub_lock:
            for member in _iter_members(event_types):
                if member not in self._subscribers:
                    self._subscribers[member] = []

    def subscribe(self, event_type, function):
        """Register *function* as a subscriber for *event_type*."""
        with self._sub_lock:
            for member in _iter_members(event_type):
                if member not in self._subscribers:
                    raise ValueError(
                        f"Unknown event type: {member}"
                    )

                if any(
                    _original_sub(s) is function for s in self._subscribers[member]
                ):
                    raise ValueError(
                        f"Function {function!r} is already subscribed to {member}"
                    )

                self._subscribers[member].append(function)

    def unsubscribe(self, event_type, function):
        """Remove *function* from the subscriber list for *event_type*."""
        with self._sub_lock:
            for member in _iter_members(event_type):
                if member not in self._subscribers:
                    raise ValueError(
                        f"Unknown event type: {member}"
                    )

                for i, s in enumerate(self._subscribers[member]):
                    if _original_sub(s) is function:
                        del self._subscribers[member][i]
                        break
                else:
                    raise ValueError(
                        f"Function {function!r} is not subscribed to {member}"
                    )

    def has_subscriber(self, event_type, function):
        """Check whether *function* is registered for *event_type*."""
        with self._sub_lock:
            for member in _iter_members(event_type):
                if member not in self._subscribers:
                    return False
                if not any(
                    _original_sub(s) is function for s in self._subscribers[member]
                ):
                    return False
            return True

    def on(self, event_type):
        """Decorator shorthand for :meth:`subscribe`.

        Usage::

            @bus.on(Event.FOO)
            def handler(event, payload):
                ...

        This is equivalent to ``bus.subscribe(Event.FOO, handler)``.
        """
        def decorator(function):
            self.subscribe(event_type, function)
            return function
        return decorator

    def clear(self, event_type):
        """Remove all subscribers for *event_type*."""
        with self._sub_lock:
            for member in _iter_members(event_type):
                if member not in self._subscribers:
                    raise ValueError(
                        f"Unknown event type: {member}"
                    )
                self._subscribers[member].clear()
