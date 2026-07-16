"""
Unit tests for the ID allocation system (IDAllocator, ClientAllocator, _resolve_global_id).

No TCP — pure logic tests to catch bugs like the id_offset/pending_requests mismatch.

How to read results:
  - PASSED  = test confirms correct behavior
  - FAILED  = test exposes a bug in the current code (expected failures below)
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from veltix.handler.rules import _resolve_global_id
from veltix.handler.rules_manager import MessageContext
from veltix.network.id_allocator import ClientAllocator, IDAllocator
from veltix.network.response import Response
from veltix.network.types import MessageType

MSG = MessageType(code=9000, name="test_id")


def _make_response(request_id: int = 0) -> Response:
    return Response(MSG, b"x", request_id=request_id)


def _make_context(
    request_id: int,
    is_server: bool = False,
    id_offset: int = 0,
) -> MessageContext:
    client = MagicMock()
    client.id_offset = id_offset
    response = _make_response(request_id)
    handler = MagicMock()
    return MessageContext(response=response, handler=handler, client=client, is_server=is_server)


# ===========================================================================
# IDAllocator — all should PASS
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

    def test_default_max_ids(self) -> None:
        assert IDAllocator().max_ids == 30000

    def test_single_id_allocator(self) -> None:
        alloc = IDAllocator(max_ids=1)
        assert alloc.allocate() == 0
        assert alloc.allocate() == 0

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
# ClientAllocator — all should PASS
# ===========================================================================


class TestClientAllocator:
    def test_first_register_is_zero(self) -> None:
        assert ClientAllocator(range_size=30000).register() == 0

    def test_sequential_indices(self) -> None:
        ca = ClientAllocator(range_size=30000)
        assert ca.register() == 0
        assert ca.register() == 1
        assert ca.register() == 2

    def test_global_id_formula(self) -> None:
        ca = ClientAllocator(range_size=30000)
        assert ca.global_id(0, 0) == 0
        assert ca.global_id(0, 5) == 5
        assert ca.global_id(1, 0) == 30000
        assert ca.global_id(1, 5) == 30005
        assert ca.global_id(2, 0) == 60000

    def test_global_id_no_collision_across_clients(self) -> None:
        ca = ClientAllocator(range_size=30000)
        idx_a = ca.register()
        idx_b = ca.register()
        assert ca.global_id(idx_a, 42) != ca.global_id(idx_b, 42)

    def test_global_id_full_range_no_overlap(self) -> None:
        ca = ClientAllocator(range_size=100)
        indices = [ca.register() for _ in range(5)]
        seen: set[int] = set()
        for idx in indices:
            for wire_id in range(100):
                gid = ca.global_id(idx, wire_id)
                assert gid not in seen
                seen.add(gid)
        assert len(seen) == 500

    def test_register_is_thread_safe(self) -> None:
        ca = ClientAllocator(range_size=30000)
        indices: list[int] = []
        lock = threading.Lock()

        def worker() -> None:
            idx = ca.register()
            with lock:
                indices.append(idx)

        threads = [threading.Thread(target=worker) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(set(indices)) == 100

    def test_custom_range_size(self) -> None:
        ca = ClientAllocator(range_size=10)
        assert ca.global_id(1, 0) == 10
        assert ca.global_id(1, 9) == 19
        assert ca.global_id(2, 0) == 20


# ===========================================================================
# _resolve_global_id — basic behavior, all should PASS
# ===========================================================================


class TestResolveGlobalID:
    def test_client_side_no_offset(self) -> None:
        ctx = _make_context(request_id=42, is_server=False)
        assert _resolve_global_id(ctx) == 42

    def test_client_side_ignores_offset(self) -> None:
        ctx = _make_context(request_id=42, is_server=False, id_offset=999)
        assert _resolve_global_id(ctx) == 42

    def test_server_side_no_client(self) -> None:
        ctx = MessageContext(
            response=_make_response(42),
            handler=MagicMock(),
            client=None,
            is_server=True,
        )
        assert _resolve_global_id(ctx) == 42

    def test_server_side_offset_zero(self) -> None:
        ctx = _make_context(request_id=42, is_server=True, id_offset=0)
        assert _resolve_global_id(ctx) == 42

    def test_server_side_ignores_offset(self) -> None:
        """Offset is not added: pending requests use raw wire_ids."""
        ctx = _make_context(request_id=42, is_server=True, id_offset=5)
        assert _resolve_global_id(ctx) == 42


# ===========================================================================
# Pending request matching
#
# These tests verify that pending request lookup works correctly.
# pending_requests is keyed by wire_id; _resolve_global_id must
# return the same wire_id so the lookup succeeds.
# ===========================================================================


class TestPendingRequestMatching:
    """
    Simulate the server send_and_wait flow:
    1. Server registers pending_requests[wire_id]
    2. Client responds with same wire_id
    3. _resolve_global_id returns wire_id (offset not used for pending)
    4. Lookup finds the pending request
    """

    def test_single_client_pending_match(self) -> None:
        """1 client (offset=0): trivially works."""
        pending = {0: "queue"}
        ctx = _make_context(request_id=0, is_server=True, id_offset=0)
        assert _resolve_global_id(ctx) in pending

    def test_two_clients_first_pending_match(self) -> None:
        """Client 0 (offset=0): global_id = wire_id → match."""
        pending = {0: "queue"}
        ctx = _make_context(request_id=0, is_server=True, id_offset=0)
        assert _resolve_global_id(ctx) in pending

    def test_two_clients_second_pending_match(self) -> None:
        """Client 1 (offset=1): offset is ignored, wire_id matches directly."""
        wire_id = 0
        pending = {wire_id: "queue"}
        ctx = _make_context(request_id=wire_id, is_server=True, id_offset=1)
        assert _resolve_global_id(ctx) in pending

    def test_various_offsets_pending_match(self) -> None:
        """For offsets 0..9, pending lookup always succeeds (offset is ignored)."""
        for offset in range(10):
            wire_id = 7
            pending = {wire_id: "queue"}
            ctx = _make_context(request_id=wire_id, is_server=True, id_offset=offset)
            assert _resolve_global_id(ctx) in pending

    def test_nonzero_wire_id_with_offset(self) -> None:
        """wire_id=5, offset=3: offset is ignored, wire_id=5 matches pending."""
        wire_id = 5
        pending = {wire_id: "queue"}
        ctx = _make_context(request_id=wire_id, is_server=True, id_offset=3)
        assert _resolve_global_id(ctx) in pending

    def test_no_cross_client_collision(self) -> None:
        """Different clients with different wire_ids resolve to different IDs."""
        ctx_a = _make_context(request_id=6, is_server=True, id_offset=0)
        ctx_b = _make_context(request_id=5, is_server=True, id_offset=1)

        gid_a = _resolve_global_id(ctx_a)
        gid_b = _resolve_global_id(ctx_b)

        assert gid_a != gid_b


# ===========================================================================
# Full simulation — end-to-end ID flow
# ===========================================================================


class TestFullSimulation:
    def test_server_initiated_find_pending(self) -> None:
        """Server allocates wire_id, registers pending, client responds. Lookup succeeds for all clients."""
        server_ids = IDAllocator(max_ids=30000)
        ca = ClientAllocator(range_size=30000)

        offset_a = ca.register()  # 0
        offset_b = ca.register()  # 1
        offset_c = ca.register()  # 2

        pending: dict[int, str] = {}

        for name, offset in [("A", offset_a), ("B", offset_b), ("C", offset_c)]:
            wire_id = server_ids.allocate()
            pending[wire_id] = f"queue_{name}"
            ctx = _make_context(request_id=wire_id, is_server=True, id_offset=offset)
            global_id = _resolve_global_id(ctx)
            assert global_id in pending, (
                f"Client {name} (offset={offset}): wire_id={wire_id} → "
                f"global_id={global_id} not found in pending {list(pending.keys())}"
            )
