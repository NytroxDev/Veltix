from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING

from ._base import Subscriber, _BaseEventBus

if TYPE_CHECKING:
    from enum import Enum


class AsyncEventBus(_BaseEventBus):
    """An async-compatible publish-subscribe event bus.

    Identical API to :class:`EventBus` except that :meth:`emit` and
    :meth:`once` support **both** sync and async subscribers.  Async
    subscribers are awaited; sync subscribers are called directly.
    A reentrant thread lock protects subscriber lists so the bus can
    be used safely across threads and tasks alike.
    """

    async def emit(
        self,
        event: Enum,
        payload: object | None = None,
    ) -> list[tuple[Subscriber, Exception]]:
        """Dispatch *event* with *payload* to all its subscribers.

        Sync subscribers are called directly; async subscribers are
        awaited.  If any subscriber raises, the remaining subscribers
        are still invoked.  Returns a list of ``(subscriber, exception)``
        for every failed call.
        """
        subs = self._get_sub(event)

        if not subs:
            return []

        failed: list[tuple[Subscriber, Exception]] = []
        for sub in subs:
            try:
                result = sub(event, payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                failed.append((sub, exc))
        return failed

    def once(
        self,
        event_type: Enum | type[Enum],
        function: Subscriber,
    ) -> None:
        """Register *function* to fire at most once for *event_type*.

        Works with both sync and async functions.  Automatically
        unsubscribes after the first :meth:`emit` — even if the
        function raises.
        """

        @functools.wraps(function)
        async def wrapper(event: Enum, payload: object | None) -> None:
            try:
                result = function(event, payload)
                if asyncio.iscoroutine(result):
                    await result
            finally:
                self.unsubscribe(event, function)

        self.subscribe(event_type, wrapper)
