import asyncio

import pytest

from veltix._vendor.avyra import AsyncEventBus

from .conftest import Event


@pytest.fixture
def async_bus() -> AsyncEventBus:
    b = AsyncEventBus()
    b.register(Event)
    return b


@pytest.mark.asyncio
class TestAsyncEmit:
    async def test_calls_sync_subscriber(self, async_bus, results, collector):
        async_bus.subscribe(Event.FOO, collector)
        await async_bus.emit(Event.FOO, "x")
        assert results == [(Event.FOO, "x")]

    async def test_calls_async_subscriber(self, async_bus, results):
        async def subscriber(event, payload):
            results.append((event, payload))

        async_bus.subscribe(Event.FOO, subscriber)
        await async_bus.emit(Event.FOO, "y")
        assert results == [(Event.FOO, "y")]

    async def test_mixed_sync_and_async(self, async_bus, results):
        results2 = []

        def sync_sub(e, p):
            results.append((e, p))

        async def async_sub(e, p):
            results2.append((e, p))

        async_bus.subscribe(Event.FOO, sync_sub)
        async_bus.subscribe(Event.FOO, async_sub)
        await async_bus.emit(Event.FOO, "z")
        assert results == [(Event.FOO, "z")]
        assert results2 == [(Event.FOO, "z")]

    async def test_continues_after_crash(self, async_bus, results, collector):
        def crash(e, p):
            raise RuntimeError("boom")

        async_bus.subscribe(Event.FOO, crash)
        async_bus.subscribe(Event.FOO, collector)
        failed = await async_bus.emit(Event.FOO, "data")
        assert len(failed) == 1
        assert results == [(Event.FOO, "data")]

    async def test_async_subscriber_crash(self, async_bus, results, collector):
        async def crash(e, p):
            raise ValueError("async boom")

        async_bus.subscribe(Event.FOO, crash)
        async_bus.subscribe(Event.FOO, collector)
        failed = await async_bus.emit(Event.FOO, "data")
        assert len(failed) == 1
        assert results == [(Event.FOO, "data")]

    async def test_calls_in_order(self, async_bus):
        order = []

        def a(e, p):
            order.append("a")

        async def b(e, p):
            await asyncio.sleep(0)
            order.append("b")

        async def c(e, p):
            order.append("c")

        async_bus.subscribe(Event.FOO, a)
        async_bus.subscribe(Event.FOO, b)
        async_bus.subscribe(Event.FOO, c)
        await async_bus.emit(Event.FOO, None)
        assert order == ["a", "b", "c"]


@pytest.mark.asyncio
class TestAsyncOnce:
    async def test_once_calls_once(self, async_bus, results, collector):
        async_bus.once(Event.FOO, collector)
        await async_bus.emit(Event.FOO, 1)
        await async_bus.emit(Event.FOO, 2)
        assert results == [(Event.FOO, 1)]

    async def test_once_with_async_func(self, async_bus, results):
        async def subscriber(event, payload):
            results.append((event, payload))

        async_bus.once(Event.FOO, subscriber)
        await async_bus.emit(Event.FOO, 1)
        await async_bus.emit(Event.FOO, 2)
        assert results == [(Event.FOO, 1)]

    async def test_once_unsubscribes_on_crash(self, async_bus, results, collector):
        def crash(e, p):
            raise RuntimeError("boom")

        async_bus.once(Event.FOO, crash)
        await async_bus.emit(Event.FOO, 1)
        async_bus.subscribe(Event.FOO, collector)
        await async_bus.emit(Event.FOO, 2)
        assert results == [(Event.FOO, 2)]

    async def test_once_unsubscribes_on_async_crash(self, async_bus, results, collector):
        async def crash(e, p):
            raise RuntimeError("async boom")

        async_bus.once(Event.FOO, crash)
        await async_bus.emit(Event.FOO, 1)
        async_bus.subscribe(Event.FOO, collector)
        await async_bus.emit(Event.FOO, 2)
        assert results == [(Event.FOO, 2)]

    async def test_once_on_class(self, async_bus, results, collector):
        async_bus.once(Event, collector)
        await async_bus.emit(Event.FOO, 1)
        assert results == [(Event.FOO, 1)]
        await async_bus.emit(Event.FOO, 2)
        assert results == [(Event.FOO, 1)]

    async def test_once_on_class_other_members_still_fire(self, async_bus, results, collector):
        async_bus.once(Event, collector)
        await async_bus.emit(Event.FOO, 1)
        await async_bus.emit(Event.BAR, 2)
        assert results == [(Event.FOO, 1), (Event.BAR, 2)]


@pytest.mark.asyncio
class TestAsyncSubscribe:
    async def test_subscribe_to_unknown_raises(self, async_bus, collector):
        from .conftest import OtherEvent

        with pytest.raises(ValueError, match="Unknown event type"):
            async_bus.subscribe(OtherEvent.X, collector)

    async def test_subscribe_twice_raises(self, async_bus, collector):
        async_bus.subscribe(Event.FOO, collector)
        with pytest.raises(ValueError, match="already subscribed"):
            async_bus.subscribe(Event.FOO, collector)

    async def test_subscribe_to_class_subscribes_all(self, async_bus, collector):
        async_bus.subscribe(Event, collector)
        assert async_bus.has_subscriber(Event.FOO, collector)
        assert async_bus.has_subscriber(Event.BAR, collector)
        assert async_bus.has_subscriber(Event.BAZ, collector)


@pytest.mark.asyncio
class TestAsyncUnsubscribe:
    async def test_unsubscribe_single(self, async_bus, collector):
        async_bus.subscribe(Event.FOO, collector)
        async_bus.unsubscribe(Event.FOO, collector)
        assert not async_bus.has_subscriber(Event.FOO, collector)

    async def test_unsubscribe_not_subscribed_raises(self, async_bus, collector):
        with pytest.raises(ValueError, match="not subscribed"):
            async_bus.unsubscribe(Event.FOO, collector)

    async def test_unsubscribe_unknown_raises(self, async_bus, collector):
        from .conftest import OtherEvent

        with pytest.raises(ValueError, match="Unknown event type"):
            async_bus.unsubscribe(OtherEvent.X, collector)


@pytest.mark.asyncio
class TestAsyncClear:
    async def test_clear_single(self, async_bus, collector):
        async_bus.subscribe(Event.FOO, collector)
        async_bus.clear(Event.FOO)
        assert async_bus.has_subscriber(Event.FOO, collector) is False

    async def test_clear_class(self, async_bus, collector):
        async_bus.subscribe(Event, collector)
        async_bus.clear(Event)
        assert async_bus.has_subscriber(Event.FOO, collector) is False
        assert async_bus.has_subscriber(Event.BAR, collector) is False
        assert async_bus.has_subscriber(Event.BAZ, collector) is False

    async def test_clear_unknown_raises(self, async_bus):
        from .conftest import OtherEvent

        with pytest.raises(ValueError, match="Unknown event type"):
            async_bus.clear(OtherEvent.X)


@pytest.mark.asyncio
class TestAsyncHasSubscriber:
    async def test_detects_sync(self, async_bus, collector):
        async_bus.subscribe(Event.FOO, collector)
        assert async_bus.has_subscriber(Event.FOO, collector) is True

    async def test_detects_async(self, async_bus):
        async def subscriber(e, p):
            pass

        async_bus.subscribe(Event.FOO, subscriber)
        assert async_bus.has_subscriber(Event.FOO, subscriber) is True

    async def test_detects_once_wrapper(self, async_bus, collector):
        async_bus.once(Event.FOO, collector)
        assert async_bus.has_subscriber(Event.FOO, collector) is True


@pytest.mark.asyncio
class TestAsyncDecorator:
    async def test_on_decorator_sync(self, async_bus, results):
        @async_bus.on(Event.FOO)
        def handler(event, payload):
            results.append((event, payload))

        await async_bus.emit(Event.FOO, "x")
        assert results == [(Event.FOO, "x")]

    async def test_on_decorator_async(self, async_bus, results):
        @async_bus.on(Event.FOO)
        async def handler(event, payload):
            results.append((event, payload))

        await async_bus.emit(Event.FOO, "y")
        assert results == [(Event.FOO, "y")]
