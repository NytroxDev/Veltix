"""Outbound messaging helpers for the Veltix client."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ..network.request import Request
from ..network.system_types import PING

if TYPE_CHECKING:
    from ..network.response import Response
    from .core import ClientCore


class ClientMessaging:
    """Outbound side of a client: send, request/response and ping helpers."""

    __slots__ = ("_core",)

    def __init__(self, core: ClientCore) -> None:
        self._core = core

    def send(self, request: Request) -> bool:
        """Send a request to the server.

        Args:
            request: Request to send.

        Returns:
            True if the send succeeded.
        """
        return self._core.sender.send(request)

    def send_and_wait(self, request: Request, timeout: float = 5.0) -> Response | None:
        """
        Send a request and block until the matching response is received.

        The request queue is registered before sending to avoid a race condition
        where the response could arrive before wait() is called.

        Args:
            request: Request to send.
            timeout: Maximum time to wait for a response in seconds (default: 5.0).

        Returns:
            Matching Response, or None on timeout or send failure.
        """
        if request.request_id is None:
            request.request_id = self._core.id_allocator.allocate()

        request_id = request.request_id
        self._core.bus.debug(f"send_and_wait: registering request {request_id}...")

        self._core.request_handler.register(request_id)

        if not self._core.sender.send(request):
            self._core.bus.error(f"Failed to send request {request_id}...")
            self._core.request_handler.unregister(request_id)
            return None

        return self._core.request_handler.wait(request_id, timeout)

    def ping_server(self, timeout: float = 5.0) -> float | None:
        """
        Ping the server and measure round-trip latency.

        Args:
            timeout: Maximum time to wait for pong in seconds (default: 5.0).

        Returns:
            Latency in milliseconds, or None on timeout.
        """
        self._core.bus.debug("Pinging server")
        request = Request(PING, b"")
        t_send = time.perf_counter()
        response = self.send_and_wait(request, timeout=timeout)
        t_recv = time.perf_counter()

        if response:
            rtt = (t_recv - t_send) * 1000
            self._core.bus.info(f"Ping: {rtt:.2f}ms")
            return rtt

        self._core.bus.warning("Ping timed out")
        return None
