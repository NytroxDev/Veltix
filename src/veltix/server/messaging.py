"""Outbound messaging helpers for the Veltix server."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from ..network.request import Request
from ..network.system_types import PING

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..network.response import Response
    from ..socket_core.base_socket import BaseSocket
    from .client_info import ClientInfo
    from .core import ServerCore


class ServerMessaging:
    """Outbound side of a server: send, broadcast and ping helpers."""

    __slots__ = ("_core",)

    def __init__(self, core: ServerCore) -> None:
        self._core = core

    def send(self, request: Request, client: ClientInfo | BaseSocket) -> bool:
        """Send a request to a client, accepting ClientInfo or BaseSocket."""
        from .client_info import ClientInfo

        socket = client.conn if isinstance(client, ClientInfo) else client
        return self._core.sender.send(request, client=socket)

    def broadcast(
        self,
        request: Request,
        except_clients: list[ClientInfo | BaseSocket] | None = None,
    ) -> bool:
        """Broadcast a request to all connected clients."""
        return self._core.sender.broadcast(request, except_clients=except_clients)

    def send_and_wait(
        self, request: Request, client: ClientInfo, timeout: float = 5.0
    ) -> Response | None:
        """Send a request and block until the matching response arrives."""
        from .client_info import ClientInfo

        if not isinstance(client, ClientInfo):
            raise TypeError(
                f"send_and_wait() target must be a ClientInfo, got {type(client).__name__}. "
                "Fix: pass the client argument of a route/on_connect callback, or "
                "pick one from server.clients - a raw socket is not enough."
            )

        if request.request_id is None:
            request.request_id = self._core.id_allocator.allocate()

        request_id = request.request_id
        self._core.bus.debug(f"send_and_wait: {request_id}... → {client.addr}")

        self._core.request_handler.register(request_id)

        if not self._core.sender.send(request, client=client.conn):
            self._core.bus.error(f"Failed to send request {request_id}... to {client.addr}")
            self._core.request_handler.unregister(request_id)
            return None

        return self._core.request_handler.wait(request_id, timeout)

    def ping_client(self, client: ClientInfo, timeout: float = 5.0) -> float | None:
        """Ping a client and measure round-trip latency."""
        self._core.bus.debug(f"Pinging client {client.addr}")
        request = Request(PING, b"")
        t_send = time.perf_counter()
        response = self.send_and_wait(request, client, timeout=timeout)
        t_recv = time.perf_counter()

        if response:
            rtt = (t_recv - t_send) * 1000
            self._core.bus.info(f"Ping {client.addr}: {rtt:.2f}ms")
            return rtt

        self._core.bus.warning(f"Ping timeout for client {client.addr}")
        return None

    def ping_client_async(
        self,
        client: ClientInfo,
        callback: Callable[[float | None], None],
        timeout: float = 5.0,
    ) -> None:
        """Ping a client in a background thread and relay the result."""

        def _ping() -> None:
            try:
                callback(self.ping_client(client, timeout=timeout))
            except Exception as e:
                self._core.bus.error(f"Error in async ping: {e}")
                callback(None)

        threading.Thread(target=_ping, daemon=True).start()
