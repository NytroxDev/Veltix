"""Client collection access for the Veltix server."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .client_info import ClientInfo
    from .core import ServerCore


class ServerClients:
    """Read and manage the live client set of a server."""

    __slots__ = ("_core",)

    def __init__(self, core: ServerCore) -> None:
        self._core = core

    @property
    def is_full(self) -> bool:
        """True when max_connection is reached (never full when unlimited)."""
        if self._core.config.max_connection < 0:
            return False
        return self._core.socket.client_manager.count() >= self._core.config.max_connection

    @property
    def clients(self) -> list[ClientInfo]:
        """Return the ClientInfo of every connected client."""
        return self._core.clients

    def close_client(self, client: ClientInfo, id_: int | None = None) -> bool:
        """Forcefully close a specific client connection."""
        if id_ is not None:
            return self._core.socket.close_client(id_)

        if not client:
            self._core.bus.warning(
                "close_client() got no client. Fix: pass a ClientInfo from "
                "server.clients or from the on_connect callback."
            )
            return False

        entry = next(
            (e for e in self._core.socket.client_manager.get_all_clients() if e.info == client),
            None,
        )
        if not entry:
            self._core.bus.warning(
                f"close_client() could not find {client.addr} in the client list. "
                "Fix: pass a ClientInfo currently present in server.clients."
            )
            return False
        return self._core.socket.close_client(entry)

    def get_clients_by_tag(self, tag: str, value: Any = None) -> list[ClientInfo]:
        """Return the clients owning a tag, optionally matching a value."""
        entries = self._core.socket.client_manager.get_clients_by_tag(tag, value)
        return [e.info for e in entries]
