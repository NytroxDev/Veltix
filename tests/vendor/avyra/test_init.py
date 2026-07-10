

from veltix._vendor.avyra import EventBus

from .conftest import Event, OtherEvent


class TestInit:
    def test_starts_empty(self):
        bus = EventBus()
        assert bus._subscribers == {}

    def test_register_class(self):
        bus = EventBus()
        bus.register(Event)
        assert list(bus._subscribers) == [Event.FOO, Event.BAR, Event.BAZ]

    def test_register_member_list(self):
        bus = EventBus()
        bus.register([Event.FOO, Event.BAR])
        assert list(bus._subscribers) == [Event.FOO, Event.BAR]

    def test_register_skips_existing(self):
        bus = EventBus()
        bus.register([Event.FOO])
        bus.register([Event.FOO, Event.BAR])
        assert list(bus._subscribers) == [Event.FOO, Event.BAR]

    def test_register_other_enum(self):
        bus = EventBus()
        bus.register(OtherEvent)
        assert list(bus._subscribers) == [OtherEvent.X, OtherEvent.Y]

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
        assert list(bus._subscribers) == [Event.FOO, Event.BAR, Event.BAZ]
