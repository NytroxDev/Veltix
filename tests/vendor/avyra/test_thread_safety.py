import threading
from enum import Enum, auto

from veltix._vendor.avyra import EventBus


class Evt(Enum):
    A = auto()
    B = auto()


def test_concurrent_subscribe_unique_functions():
    bus = EventBus()
    bus.register(Evt)
    results = []
    lock = threading.Lock()

    def make_subscriber(i):
        def subscriber(event, payload):
            with lock:
                results.append(i)

        return subscriber

    n = 50
    threads = []

    for i in range(n):
        fn = make_subscriber(i)
        t = threading.Thread(target=bus.subscribe, args=(Evt.A, fn))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    failed = bus.emit(Evt.A, "x")
    assert failed == []
    assert len(results) == n


def test_concurrent_emit_and_unsubscribe():
    bus = EventBus()
    bus.register(Evt)
    results = []
    lock = threading.Lock()

    def subscriber(event, payload):
        with lock:
            results.append(payload)

    bus.subscribe(Evt.A, subscriber)
    bus.subscribe(Evt.A, lambda e, p: None)  # extra subscriber

    barrier = threading.Barrier(2)

    def emit_thread():
        barrier.wait()
        bus.emit(Evt.A, "x")

    def unsubscribe_thread():
        barrier.wait()
        bus.unsubscribe(Evt.A, subscriber)

    t1 = threading.Thread(target=emit_thread)
    t2 = threading.Thread(target=unsubscribe_thread)
    t1.start()
    t2.start()
    t1.join()
    t2.join()


def test_concurrent_subscribe_and_has_subscriber():
    bus = EventBus()
    bus.register(Evt)

    def subscriber(event, payload):
        pass

    bus.subscribe(Evt.A, subscriber)

    def check():
        for _ in range(100):
            assert bus.has_subscriber(Evt.A, subscriber)

    threads = [threading.Thread(target=check) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def test_reentrant_lock_subscribe_during_emit():
    bus = EventBus()
    bus.register(Evt)
    inner_called = False

    def inner(event, payload):
        nonlocal inner_called
        inner_called = True

    def outer(event, payload):
        bus.subscribe(Evt.A, inner)  # reentrant: same thread, same lock

    bus.subscribe(Evt.A, outer)
    failed = bus.emit(Evt.A, None)
    assert failed == []
    # inner is subscribed during emit but the snapshot already
    # captured the subscriber list, so it fires on the *next* emit
    assert not inner_called
    bus.emit(Evt.A, None)
    assert inner_called
