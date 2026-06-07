from ..logger.core import Logger
from ..network.request import Request
from ..network.system_types import HELLO, PING, PONG
from .rules_manager import MessageContext, Rule


class PingRule(Rule):
    _logger = Logger.get_instance()

    def handle(self, context: MessageContext) -> None:
        self._logger.debug(
            f"Responding to PING with PONG (request_id={context.response.request_id})"
        )
        pong = Request(PONG, b"", request_id=context.response.request_id)
        if context.is_server:
            context.handler.sender.send(pong, client=context.client.conn)
        else:
            context.handler.sender.send(pong)

    def can_handle(self, context: MessageContext) -> bool:
        return context.response.type == PING


class HelloRule(Rule):
    _logger = Logger.get_instance()

    def handle(self, context: MessageContext) -> None:
        ok = context.handler.handshake_handler.handle_hello(context.response)
        if ok:
            context.handler.handshake_handler.send_hello_ack(context.response.request_id)
            if context.handler.on_handshake_done:
                try:
                    context.handler.on_handshake_done()
                except Exception as e:
                    self._logger.error(f"Error in on_handshake_done: {e}")
        else:
            self._logger.warning("[Handshake] HELLO invalid — closing connection")
            if context.handler.sender.conn:
                context.handler.sender.conn.close()

    def can_handle(self, context: MessageContext) -> bool:
        return context.response.type == HELLO and not context.is_server


class PendingRequestRule(Rule):
    _logger = Logger.get_instance()

    def handle(self, context: MessageContext) -> None:
        self._logger.debug(
            f"Routing response to pending request (request_id={context.response.request_id})"
        )
        with context.handler.pending_requests_lock:
            queue = context.handler.pending_requests.get(context.response.request_id)
        if queue:
            queue.put(context.response)

    def can_handle(self, context: MessageContext) -> bool:
        return False

    def try_handle(self, context: MessageContext) -> bool:
        with context.handler.pending_requests_lock:
            queue = context.handler.pending_requests.get(context.response.request_id)
        if queue is None:
            return False
        queue.put(context.response)
        self._logger.debug(
            f"Routing response to pending request (request_id={context.response.request_id})"
        )
        return True


class RouteRule(Rule):
    _logger = Logger.get_instance()

    def handle(self, context: MessageContext) -> None:
        self._logger.debug(f"Dispatching to registered route for type {context.response.type}")
        if context.is_server:
            context.handler._executor.submit(
                context.handler._routes[context.response.type], context.client, context.response
            )
        else:
            context.handler._executor.submit(
                context.handler._routes[context.response.type], context.response
            )

    def can_handle(self, context: MessageContext) -> bool:
        return context.response.type in context.handler._routes


class OnRecvRule(Rule):
    def handle(self, context: MessageContext) -> None:
        if context.is_server:
            context.handler._executor.submit(
                context.handler.on_recv, context.client, context.response
            )
        else:
            context.handler._executor.submit(context.handler.on_recv, context.response)

    def can_handle(self, context: MessageContext) -> bool:
        return context.handler.on_recv is not None


class UnhandledRule(Rule):
    _logger = Logger.get_instance()

    def handle(self, context: MessageContext) -> None:
        if context.is_server:
            addr = getattr(context.client, "addr", "unknown")
            src = f"client {addr}"
        else:
            src = "server"
        self._logger.warning(f"No handler registered for message from {src}")

    def can_handle(self, context: MessageContext) -> bool:
        return True


ALL_RULES = [
    PingRule(),
    HelloRule(),
    PendingRequestRule(),
    RouteRule(),
    OnRecvRule(),
    UnhandledRule(),
]
