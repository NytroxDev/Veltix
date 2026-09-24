"""
Unit tests for the pending-safe ID allocation system.

No TCP: pure logic tests to verify that IDAllocator never reuses a request
ID while it is still tracked as pending by a send_and_wait in flight.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from veltix.exceptions import IDsExhaustedError
from veltix.handler.rules_manager import MessageContext
from veltix.network.id_allocator import IDAllocator
from veltix.network.response import Response
from veltix.network.types import MessageType

MSG = MessageType(code=9000, name="test_id")


def _make_response(request_id: int = 0) -> Response:
    return Response(MSG, b"x", request_id=request_id)


def _make_context(request_id: int, is_server: bool = False) -> MessageContext:
    client = MagicMock()
    response = _make_response(request_id)
    handler = MagicMock()
    return MessageContext(response=response, handler=handler, client=client, is_server=is_server)


# ===========================================================================
# IDAllocator - no pending: sequential behavior is unchanged
# ===========================================================================


class TestIDAllocator:
    def test_first_id_is_zero(self) -> None:
        assert IDAllocator(max_ids=100).allocate() == 0

    def test_sequential(self) -> None:
        alloc = IDAllocator(max_ids=100)
        for i in range(10):
            assert alloc.allocate() == i

    def test_wrap_around(self) -> None:
        alloc = IDAllocator(max_ids=5)
        ids = [alloc.allocate() for _ in range(10)]
        assert ids == [0, 1, 2, 3, 4, 0, 1, 2, 3, 4]

    def test_wrap_around_exactly(self) -> None:
        alloc = IDAllocator(max_ids=3)
        assert alloc.allocate() == 0
        assert alloc.allocate() == 1
        assert alloc.allocate() == 2
        assert alloc.allocate() == 0

    def test_max_ids_property(self) -> None:
        assert IDAllocator(max_ids=42).max_ids == 42

    def test_default_max_ids_is_full_uint16(self) -> None:
        assert IDAllocator().max_ids == 65535

    def test_max_ids_setter(self) -> None:
        alloc = IDAllocator(max_ids=100)
        alloc.max_ids = 6
        assert [alloc.allocate() for _ in range(7)] == [0, 1, 2, 3, 4, 5, 0]

    def test_single_id_allocator(self) -> None:
        alloc = IDAllocator(max_ids=1)
        assert alloc.allocate() == 0
        assert alloc.allocate() == 0

    def test_no_pending_means_sequential(self) -> None:
        alloc = IDAllocator(max_ids=5, is_pending=lambda _: False)
        ids = [alloc.allocate() for _ in range(6)]
        assert ids == [0, 1, 2, 3, 4, 0]

    def test_thread_safety_all_ids_in_range(self) -> None:
        alloc = IDAllocator(max_ids=50)
        results: list[int] = []
        lock = threading.Lock()

        def worker() -> None:
            for _ in range(200):
                val = alloc.allocate()
                with lock:
                    results.append(val)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(0 <= x < 50 for x in results)
        assert len(results) == 1600


# ===========================================================================
# Pending-safe allocator - the new behavior
# ===========================================================================


class TestPendingSafeAllocator:
    def test_pending_ids_are_skipped(self) -> None:
        pending = {2, 3}
        alloc = IDAllocator(max_ids=10, is_pending=lambda rid: rid in pending)
        assert [alloc.allocate() for _ in range(4)] == [0, 1, 4, 5]

    def test_untrack_makes_id_available(self) -> None:
        pending = {0}
        alloc = IDAllocator(max_ids=3, is_pending=lambda rid: rid in pending)
        assert alloc.allocate() == 1
        pending.clear()
        assert alloc.allocate() == 2
        assert alloc.allocate() == 0

    def test_wrap_around_with_active_pending(self) -> None:
        pending = {0, 1}
        alloc = IDAllocator(max_ids=5, is_pending=lambda rid: rid in pending)
        assert [alloc.allocate() for _ in range(3)] == [2, 3, 4]
        assert alloc.allocate() == 2

    def test_all_pending_raises(self) -> None:
        alloc = IDAllocator(max_ids=3, is_pending=lambda _: True)
        with pytest.raises(IDsExhaustedError):
            alloc.allocate()

    def test_dynamic_pending_lookup_per_allocate(self) -> None:
        calls: list[int] = []

        def is_pending(rid: int) -> bool:
            calls.append(rid)
            return rid == 1

        alloc = IDAllocator(max_ids=5, is_pending=is_pending)
        assert alloc.allocate() == 0
        assert alloc.allocate() == 2
        assert 1 in calls

    def test_thread_safety_pending_concurrent(self) -> None:
        pending_lock = threading.Lock()
        pending: set[int] = set()
        alloc = IDAllocator(max_ids=64, is_pending=lambda rid: rid in pending)
        results: list[int] = []
        errors: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            for _ in range(2000):
                value = alloc.allocate()
                with pending_lock:
                    if value in pending:
                        with lock:
                            errors.append(f"reused pending id {value}")
                    pending.add(value)
                    pending.discard(value)
                    with lock:
                        results.append(value)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(results) == 16000


# ===========================================================================
# Full simulation - request IDs are matched directly, no global ID indirection
# ===========================================================================


class TestFullSimulation:
    def test_server_initiated_find_pending(self) -> None:
        """Server allocates IDs, registers pending, client responds. Lookup succeeds."""
        server_ids = IDAllocator(max_ids=30000)
        pending: dict[int, str] = {}

        for name in ("A", "B", "C"):
            wire_id = server_ids.allocate()
            pending[wire_id] = f"queue_{name}"
            ctx = _make_context(request_id=wire_id, is_server=True)
            assert ctx.response.request_id in pending
