from ..exceptions import SenderError
from ..internal.events import MessageEvent, ProtocolEvent
from ..network.request import Request
from ..network.system_types import PING, PONG
from .rules_manager import MessageContext, Rule


def _resolve_global_id(context: MessageContext) -> int:
    """Resolve the wire request ID for pending request matching.

    Pending requests are always server-initiated: the server allocates
    wire IDs from its own ``IDAllocator`` which already produces unique
    IDs across all clients, so no client offset is needed.
    """
    return context.response.request_id


class PingRule(Rule):
    """Responds to PING messages with a PONG carrying the same request ID."""

    def handle(self, context: MessageContext) -> None:
        context.handler.bus.emit(
            ProtocolEvent.PING,
            {
                "request_id": context.response.request_id,
                "from": "client" if context.is_server else "server",
            },
        )
        context.handler.bus.debug(
            f"Responding to PING with PONG (request_id={context.response.request_id})"
        )
        pong = Request(PONG, b"", request_id=context.response.request_id)
        sender = context.handler.sender
        if sender is None:
            raise SenderError("Cannot respond to PING: sender is not initialised")
        if context.is_server:
            client = context.client
            if client is None:
                raise SenderError("Cannot respond to PING: client info is missing")
            sender.send(pong, client=client.conn)
        else:
            sender.send(pong)
        context.handler.bus.emit(
            ProtocolEvent.PONG,
            {
                "request_id": context.response.request_id,
            },
        )

    def can_handle(self, context: MessageContext) -> bool:
        """Return True if the message is a PING."""
        return context.response.type == PING


class PendingRequestRule(Rule):
    """Routes responses to a pending ``send_and_wait`` request queue."""

    def can_handle(self, context: MessageContext) -> bool:
        global_id = _resolve_global_id(context)
        with context.handler.pending_requests_lock:
            return global_id in context.handler.pending_requests

    def handle(self, context: MessageContext) -> None:
        """No-op; the real work happens in :meth:`try_handle`."""
        pass

    def try_handle(self, context: MessageContext) -> bool:
        """Check for a matching pending request and deliver the response.

        Args:
            context: The message context to process.

        Returns:
            True if a pending request was satisfied.
        """
        global_id = _resolve_global_id(context)
        with context.handler.pending_requests_lock:
            queue = context.handler.pending_requests.get(global_id)
        if queue is None:
            return False
        queue.put(context.response)
        context.handler.bus.emit(
            MessageEvent.PENDING_SATISFIED,
            {
                "request_id": global_id,
            },
        )
        context.handler.bus.debug(f"Routing response to pending request (global_id={global_id})")
        return True


class RouteRule(Rule):
    """Dispatches a message to its registered route handler."""

    def handle(self, context: MessageContext) -> None:
        context.handler.bus.debug(
            f"Dispatching to registered route for type {context.response.type}"
        )
        route = context.handler.get_route(context.response.type)
        if route is None:
            context.handler.bus.warning(
                f"Route for type {context.response.type} disappeared before dispatch"
            )
            return
        context.handler.bus.emit(
            MessageEvent.ROUTED,
            {
                "type": context.response.type,
                "route": "registered",
                "source": "server" if context.is_server else "client",
            },
        )
        if context.is_server:
            context.handler._executor.submit(route, context.client, context.response)
        else:
            context.handler._executor.submit(route, context.response)

    def can_handle(self, context: MessageContext) -> bool:
        """Return True if a route is registered for this message type."""
        return context.handler.has_route(context.response.type)


class OnRecvRule(Rule):
    """Falls back to the generic ``on_recv`` callback when no specific route exists."""

    def handle(self, context: MessageContext) -> None:
        on_recv = context.handler.on_recv
        assert on_recv is not None
        context.handler.bus.emit(
            MessageEvent.ROUTED,
            {
                "type": context.response.type,
                "route": "on_recv",
                "source": "server" if context.is_server else "client",
            },
        )
        if context.is_server:
            context.handler._executor.submit(on_recv, context.client, context.response)
        else:
            context.handler._executor.submit(on_recv, context.response)

    def can_handle(self, context: MessageContext) -> bool:
        """Return True if an ``on_recv`` callback is registered."""
        return context.handler.on_recv is not None


class UnhandledRule(Rule):
    """Logs a warning when no handler can process the message."""

    def handle(self, context: MessageContext) -> None:
        if context.is_server:
            addr = getattr(context.client, "addr", "unknown")
            src = f"client {addr}"
        else:
            src = "server"
        context.handler.bus.emit(
            MessageEvent.UNHANDLED,
            {
                "type": context.response.type,
                "length": len(context.response.content),
                "source": "server" if context.is_server else "client",
            },
        )
        context.handler.bus.warning(f"No handler registered for message from {src}")

    def can_handle(self, context: MessageContext) -> bool:
        """Always returns True — this is the catch-all rule."""
        return True


ALL_RULES = [
    PingRule(),
    PendingRequestRule(),
    RouteRule(),
    OnRecvRule(),
    UnhandledRule(),
]
"""Default rule chain evaluated in order during message processing."""
