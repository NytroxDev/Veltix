from veltix._vendor.avyra import EventBus

from .conftest import Event, OtherEvent


def _noop(event, payload):
    pass


class TestInit:
    def test_starts_empty(self):
        bus = EventBus()
        assert bus.has_subscriber(Event.FOO, _noop) is False

    def test_register_class(self):
        bus = EventBus()
        bus.register(Event)
        assert bus.has_subscriber(Event.FOO, _noop) is False
        bus.subscribe(Event.FOO, _noop)
        assert bus.has_subscriber(Event.FOO, _noop) is True

    def test_register_member_list(self):
        bus = EventBus()
        bus.register([Event.FOO, Event.BAR])
        bus.subscribe(Event.FOO, _noop)
        assert bus.has_subscriber(Event.FOO, _noop) is True

    def test_register_skips_existing(self):
        bus = EventBus()
        bus.register([Event.FOO])
        bus.register([Event.FOO, Event.BAR])
        bus.subscribe(Event.BAR, _noop)
        assert bus.has_subscriber(Event.BAR, _noop) is True

    def test_register_other_enum(self):
        bus = EventBus()
        bus.register(OtherEvent)
        bus.subscribe(OtherEvent.X, _noop)
        assert bus.has_subscriber(OtherEvent.X, _noop) is True

    def test_register_allows_subscribe_after(self):
        bus = EventBus()
        bus.register(Event)

        def handler(e, p):
            pass

        bus.subscribe(Event.FOO, handler)
        assert bus.has_subscriber(Event.FOO, handler)

    def test_register_class_doesnt_raise_on_already(self):
        bus = EventBus()
        bus.register(Event)
        bus.register(Event)  # no error
        bus.subscribe(Event.FOO, _noop)
        assert bus.has_subscriber(Event.FOO, _noop) is True
