import pytest

from veltix._vendor.avyra import EventBus
from .conftest import Event, OtherEvent


class TestSubscribe:
    def test_subscribe_single(self, bus: EventBus, collector):
        bus.subscribe(Event.FOO, collector)
        assert bus.has_subscriber(Event.FOO, collector)

    def test_subscribe_twice_raises(self, bus: EventBus, collector):
        bus.subscribe(Event.FOO, collector)
        with pytest.raises(ValueError, match="already subscribed"):
            bus.subscribe(Event.FOO, collector)

    def test_subscribe_to_unknown_raises(self, bus: EventBus, collector):
        with pytest.raises(ValueError, match="Unknown event type"):
            bus.subscribe(OtherEvent.X, collector)

    def test_subscribe_to_class_subscribes_all(self, bus: EventBus, collector):
        bus.subscribe(Event, collector)
        assert bus.has_subscriber(Event.FOO, collector)
        assert bus.has_subscriber(Event.BAR, collector)
        assert bus.has_subscriber(Event.BAZ, collector)

    def test_subscribe_to_class_duplicate_raises(self, bus: EventBus, collector):
        bus.subscribe(Event, collector)
        with pytest.raises(ValueError, match="already subscribed"):
            bus.subscribe(Event, collector)


class TestUnsubscribe:
    def test_unsubscribe_single(self, bus: EventBus, collector):
        bus.subscribe(Event.FOO, collector)
        bus.unsubscribe(Event.FOO, collector)
        assert not bus.has_subscriber(Event.FOO, collector)

    def test_unsubscribe_not_subscribed_raises(self, bus: EventBus, collector):
        with pytest.raises(ValueError, match="not subscribed"):
            bus.unsubscribe(Event.FOO, collector)

    def test_unsubscribe_unknown_raises(self, bus: EventBus, collector):
        with pytest.raises(ValueError, match="Unknown event type"):
            bus.unsubscribe(OtherEvent.X, collector)

    def test_unsubscribe_class_removes_all(self, bus: EventBus, collector):
        bus.subscribe(Event, collector)
        bus.unsubscribe(Event, collector)
        assert not bus.has_subscriber(Event.FOO, collector)
        assert not bus.has_subscriber(Event.BAR, collector)
        assert not bus.has_subscriber(Event.BAZ, collector)


class TestEmit:
    def test_emit_calls_subscriber(self, bus: EventBus, results: list, collector):
        bus.subscribe(Event.FOO, collector)
        failed = bus.emit(Event.FOO, "hello")
        assert failed == []
        assert results == [(Event.FOO, "hello")]

    def test_emit_with_none_payload(self, bus: EventBus, results: list, collector):
        bus.subscribe(Event.FOO, collector)
        bus.emit(Event.FOO)
        assert results == [(Event.FOO, None)]

    def test_emit_no_subscribers_returns_empty(self, bus: EventBus):
        failed = bus.emit(Event.FOO, "x")
        assert failed == []

    def test_emit_catches_exception(self, bus: EventBus):
        def crash(event, payload):
            raise RuntimeError("boom")

        bus.subscribe(Event.FOO, crash)
        failed = bus.emit(Event.FOO, "x")
        assert len(failed) == 1
        assert failed[0][0] is crash
        assert isinstance(failed[0][1], RuntimeError)

    def test_emit_continues_after_crash(self, bus: EventBus, results, collector):
        def crash(event, payload):
            raise ValueError("oops")

        bus.subscribe(Event.FOO, crash)
        bus.subscribe(Event.FOO, collector)
        failed = bus.emit(Event.FOO, "data")
        assert len(failed) == 1
        assert results == [(Event.FOO, "data")]

    def test_emit_order(self, bus: EventBus):
        order = []

        def a(e, p):
            order.append("a")

        def b(e, p):
            order.append("b")

        bus.subscribe(Event.FOO, a)
        bus.subscribe(Event.FOO, b)
        bus.emit(Event.FOO)
        assert order == ["a", "b"]

    def test_emit_multiple_subscribers_all_succeed(self, bus: EventBus, results, collector):
        bus.subscribe(Event.FOO, collector)
        bus.subscribe(Event.BAR, collector)
        bus.emit(Event.FOO, 1)
        bus.emit(Event.BAR, 2)
        assert results == [(Event.FOO, 1), (Event.BAR, 2)]


class TestOnce:
    def test_once_calls_once(self, bus: EventBus, results, collector):
        bus.once(Event.FOO, collector)
        bus.emit(Event.FOO, 1)
        bus.emit(Event.FOO, 2)
        assert results == [(Event.FOO, 1)]

    def test_once_unsubscribes_after_emit(self, bus: EventBus, collector):
        bus.once(Event.FOO, collector)
        bus.emit(Event.FOO, 1)
        assert not bus.has_subscriber(Event.FOO, collector)

    def test_once_still_unsubscribes_on_crash(self, bus: EventBus, results, collector):
        def crash(event, payload):
            raise RuntimeError("boom")

        bus.once(Event.FOO, crash)
        bus.emit(Event.FOO, 1)  # crash, but unsubscribes
        bus.subscribe(Event.FOO, collector)
        bus.emit(Event.FOO, 2)
        assert results == [(Event.FOO, 2)]

    def test_once_on_class(self, bus: EventBus, results, collector):
        bus.once(Event, collector)
        bus.emit(Event.FOO, 1)
        assert results == [(Event.FOO, 1)]
        bus.emit(Event.FOO, 2)  # already fired once, no more
        assert results == [(Event.FOO, 1)]

    def test_once_on_class_other_members_still_fire(self, bus: EventBus, results, collector):
        bus.once(Event, collector)
        bus.emit(Event.FOO, 1)
        bus.emit(Event.BAR, 2)
        assert results == [(Event.FOO, 1), (Event.BAR, 2)]

    def test_has_subscriber_detects_once(self, bus: EventBus, collector):
        bus.once(Event.FOO, collector)
        assert bus.has_subscriber(Event.FOO, collector) is True

    def test_unsubscribe_removes_once_wrapper(self, bus: EventBus, collector):
        bus.once(Event.FOO, collector)
        bus.unsubscribe(Event.FOO, collector)
        assert bus.has_subscriber(Event.FOO, collector) is False


class TestHasSubscriber:
    def test_false_when_not_subscribed(self, bus: EventBus, collector):
        assert bus.has_subscriber(Event.FOO, collector) is False

    def test_true_when_subscribed(self, bus: EventBus, collector):
        bus.subscribe(Event.FOO, collector)
        assert bus.has_subscriber(Event.FOO, collector) is True

    def test_false_after_unsubscribe(self, bus: EventBus, collector):
        bus.subscribe(Event.FOO, collector)
        bus.unsubscribe(Event.FOO, collector)
        assert bus.has_subscriber(Event.FOO, collector) is False

    def test_for_class_true_when_all_subscribed(self, bus: EventBus, collector):
        bus.subscribe(Event, collector)
        assert bus.has_subscriber(Event, collector) is True

    def test_for_class_false_when_missing_one(self, bus: EventBus, collector):
        bus.subscribe(Event.FOO, collector)
        bus.subscribe(Event.BAR, collector)
        assert bus.has_subscriber(Event, collector) is False

    def test_false_with_other_function(self, bus: EventBus, collector):
        other = lambda e, p: None
        bus.subscribe(Event.FOO, collector)
        assert bus.has_subscriber(Event.FOO, other) is False

    def test_unknown_event_returns_false(self, bus: EventBus, collector):
        assert bus.has_subscriber(OtherEvent.X, collector) is False

    def test_for_class_unknown_member_returns_false(self, bus: EventBus, collector):
        assert bus.has_subscriber(OtherEvent, collector) is False


class TestClear:
    def test_clear_single(self, bus: EventBus, collector):
        bus.subscribe(Event.FOO, collector)
        bus.clear(Event.FOO)
        assert bus.has_subscriber(Event.FOO, collector) is False

    def test_clear_class(self, bus: EventBus, collector):
        bus.subscribe(Event, collector)
        bus.clear(Event)
        assert bus.has_subscriber(Event.FOO, collector) is False
        assert bus.has_subscriber(Event.BAR, collector) is False
        assert bus.has_subscriber(Event.BAZ, collector) is False

    def test_clear_unknown_raises(self, bus: EventBus):
        with pytest.raises(ValueError, match="Unknown event type"):
            bus.clear(OtherEvent.X)


class TestDecorator:
    def test_on_decorator(self, bus: EventBus, results):
        @bus.on(Event.FOO)
        def handler(event, payload):
            results.append((event, payload))

        bus.emit(Event.FOO, "x")
        assert results == [(Event.FOO, "x")]
        assert bus.has_subscriber(Event.FOO, handler)

    def test_on_decorator_class(self, bus: EventBus, results):
        @bus.on(Event)
        def handler(event, payload):
            results.append((event, payload))

        bus.emit(Event.FOO, 1)
        bus.emit(Event.BAR, 2)
        assert results == [(Event.FOO, 1), (Event.BAR, 2)]

    def test_on_decorator_duplicate_raises(self, bus: EventBus):
        @bus.on(Event.FOO)
        def handler(event, payload):
            pass

        with pytest.raises(ValueError, match="already subscribed"):
            bus.subscribe(Event.FOO, handler)
