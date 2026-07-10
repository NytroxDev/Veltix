from __future__ import annotations

from typing import TYPE_CHECKING

from ._base import Subscriber, _BaseEventBus

if TYPE_CHECKING:
    from enum import Enum


class EventBus(_BaseEventBus):
    """A thread-safe publish-subscribe event bus.

    Allows decoupled communication between components by letting them
    subscribe to typed events (``Enum`` members) and emit events with an
    optional payload to all registered subscribers.
    All subscriber list mutations are protected by an reentrant lock; the
    actual dispatch iterates over a snapshot copy to avoid holding the
    lock during callback execution.
    """

    def emit(
            self,
            event: Enum,
            payload: object = None,
    ) -> list[tuple[Subscriber, Exception]]:
        """Dispatch *event* with *payload* to all its subscribers.

        Subscribers are invoked synchronously in registration order. A
        snapshot of the subscriber list is taken under the lock so that
        concurrent modifications do not affect the current dispatch.

        If a subscriber raises an exception, it is caught and the
        remaining subscribers are still called.  The list of failed
        subscribers together with their exceptions is returned.

        Args:
            event: The ``Enum`` member identifying the event type.
            payload: An optional data payload passed to every subscriber.

        Returns:
            A list of ``(subscriber, exception)`` pairs for every
            subscriber that raised during dispatch.  Empty if all
            succeeded.
        """
        subs = self._get_sub(event)

        if not subs:
            return []

        failed: list[tuple[Subscriber, Exception]] = []
        for sub in subs:
            try:
                sub(event, payload)
            except Exception as exc:
                failed.append((sub, exc))
        return failed

    def once(
            self,
            event_type,
            function: Subscriber,
    ) -> None:
        """Register *function* to fire at most once for *event_type*.

        The function is automatically unsubscribed after the first
        :meth:`emit`.  If *event_type* is an ``Enum`` class, a separate
        one-shot registration is created for **each** member — each
        member fires independently once.

        Args:
            event_type: An ``Enum`` member or an ``Enum`` class.
            function: The callable to invoke once.

        Raises:
            TypeError: If *event_type* is neither an ``Enum`` member
                nor an ``Enum`` class.
            ValueError: If a member is unknown.
        """
        def wrapper(event: Enum, payload: object) -> None:
            try:
                function(event, payload)
            finally:
                self.unsubscribe(event, function)

        wrapper._original = function  # type: ignore[attr-defined]
        self.subscribe(event_type, wrapper)
