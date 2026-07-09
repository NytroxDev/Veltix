from enum import Enum, auto

import pytest

from veltix._vendor.avyra import EventBus


class Event(Enum):
    FOO = auto()
    BAR = auto()
    BAZ = auto()


class OtherEvent(Enum):
    X = auto()
    Y = auto()


@pytest.fixture
def bus() -> EventBus:
    b = EventBus()
    b.register(Event)
    return b


@pytest.fixture
def bus_all() -> EventBus:
    b = EventBus()
    b.register([Event.FOO, Event.BAR, Event.BAZ])
    return b


@pytest.fixture
def results() -> list:
    return []


@pytest.fixture
def collector(results: list) -> callable:
    def _(event, payload):
        results.append((event, payload))
    return _
