"""Unit tests for the benchmark interrupt-time server cleanup."""

from __future__ import annotations

from veltix.benchmark import utils


class _FakeServer:
    def __init__(self) -> None:
        self.closed = 0

    def close_all(self) -> None:
        self.closed += 1


class TestServerCleanup:
    def test_track_untrack(self) -> None:
        server = _FakeServer()
        utils.track(server)
        assert server in utils._live
        utils.untrack(server)
        assert server not in utils._live

    def test_cleanup_closes_tracked_servers(self) -> None:
        utils.cleanup()  # reset state
        server = _FakeServer()
        utils.track(server)
        utils.cleanup()
        assert server.closed == 1
        assert utils._live == []

    def test_cleanup_closes_in_reverse_order(self) -> None:
        utils.cleanup()  # reset state
        first = _FakeServer()
        second = _FakeServer()
        utils.track(first)
        utils.track(second)
        utils.cleanup()
        order = [second.closed > 0, first.closed > 0]
        assert order == [True, True]

    def test_cleanup_survives_close_errors(self) -> None:
        utils.cleanup()  # reset state

        class _Broken:
            def close_all(self) -> None:
                raise RuntimeError("boom")

        utils.track(_Broken())
        utils.cleanup()  # must not raise
        assert utils._live == []

    def test_cleanup_ignores_untracked_servers(self) -> None:
        utils.cleanup()  # reset state
        server = _FakeServer()
        utils.track(server)
        utils.untrack(server)
        utils.cleanup()
        assert server.closed == 0
        assert utils._live == []
