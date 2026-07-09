from ..internal.events import ProtocolEvent
from ..network.request import Request
from ..network.system_types import PING, PONG
from .rules_manager import MessageContext, Rule


class PingRule(Rule):
    def handle(self, context: MessageContext) -> None:
        context.handler.bus.emit(ProtocolEvent.PING, {
            "request_id": context.response.request_id.hex(),
            "from": "client" if context.is_server else "server",
        })
        context.handler.bus.debug(
            f"Responding to PING with PONG (request_id={context.response.request_id.hex()})"
        )
        pong = Request(PONG, b"", request_id=context.response.request_id)
        sender = context.handler.sender
        assert sender is not None
        if context.is_server:
            client = context.client
            assert client is not None
            sender.send(pong, client=client.conn)
        else:
            sender.send(pong)
        context.handler.bus.emit(ProtocolEvent.PONG, {
            "request_id": context.response.request_id.hex(),
        })

    def can_handle(self, context: MessageContext) -> bool:
        return context.response.type == PING


class PendingRequestRule(Rule):
    def can_handle(self, context: MessageContext) -> bool:
        with context.handler.pending_requests_lock:
            return context.response.request_id in context.handler.pending_requests

    def handle(self, context: MessageContext) -> None:
        pass

    def try_handle(self, context: MessageContext) -> bool:
        with context.handler.pending_requests_lock:
            queue = context.handler.pending_requests.get(context.response.request_id)
        if queue is None:
            return False
        queue.put(context.response)
        context.handler.bus.debug(
            f"Routing response to pending request (request_id={context.response.request_id.hex()})"
        )
        return True


class RouteRule(Rule):
    def handle(self, context: MessageContext) -> None:
        context.handler.bus.debug(f"Dispatching to registered route for type {context.response.type}")
        route = context.handler.get_route(context.response.type)
        if route is None:
            context.handler.bus.warning(
                f"Route for type {context.response.type} disappeared before dispatch"
            )
            return
        if context.is_server:
            context.handler._executor.submit(route, context.client, context.response)
        else:
            context.handler._executor.submit(route, context.response)

    def can_handle(self, context: MessageContext) -> bool:
        return context.handler.has_route(context.response.type)


class OnRecvRule(Rule):
    def handle(self, context: MessageContext) -> None:
        on_recv = context.handler.on_recv
        assert on_recv is not None
        if context.is_server:
            context.handler._executor.submit(on_recv, context.client, context.response)
        else:
            context.handler._executor.submit(on_recv, context.response)

    def can_handle(self, context: MessageContext) -> bool:
        return context.handler.on_recv is not None


class UnhandledRule(Rule):
    def handle(self, context: MessageContext) -> None:
        if context.is_server:
            addr = getattr(context.client, "addr", "unknown")
            src = f"client {addr}"
        else:
            src = "server"
        context.handler.bus.warning(f"No handler registered for message from {src}")

    def can_handle(self, context: MessageContext) -> bool:
        return True


ALL_RULES = [
    PingRule(),
    PendingRequestRule(),
    RouteRule(),
    OnRecvRule(),
    UnhandledRule(),
]
