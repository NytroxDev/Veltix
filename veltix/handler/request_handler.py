"""Request handling and routing for incoming messages."""

from __future__ import annotations

from queue import Empty, Queue
from threading import Lock
from typing import TYPE_CHECKING, Callable, Optional, Union

from ..handler.callback_executor import CallbackExecutor
from ..handler.handshake_handler import HandshakeHandler
from ..internal.events import ErrorEvent, MessageEvent
from ..internal.mode import Mode
from .rules import ALL_RULES
from .rules_manager import MessageContext, RulesManager

if TYPE_CHECKING:
    from ..internal.bus import VeltixBus
    from ..network.request import Response
    from ..network.sender import Sender
    from ..network.types import MessageType
    from ..server.client_info import ClientInfo


class RequestHandler:
    """
    Routes incoming messages, correlates request/response pairs, and dispatches callbacks.

    Processing order for each message:
    1. Auto-respond to PING with PONG
    2. Deliver to pending queue if send_and_wait() is waiting
    3. Dispatch to a registered route if one matches
    4. Fall back to default on_recv callback
    5. Log a warning if nothing handled the message
    """

    def __init__(
        self,
        mode: Union[Mode, str],
        bus: VeltixBus,
        max_workers: int = 4,
        sender: Optional[Sender] = None,
    ) -> None:
        if isinstance(mode, str):
            mode = Mode(mode)
        self.bus = bus
        self.on_recv = None
        self.mode = mode
        self.is_server = self.mode == Mode.SERVER
        self.sender = sender

        self.handshake_handler = HandshakeHandler(mode=mode, bus=self.bus)
        self._executor = CallbackExecutor(max_workers=max_workers, bus=self.bus)

        self.pending_requests: dict[bytes, Queue] = {}
        self.pending_requests_lock = Lock()

        self._routes: dict[MessageType, Callable] = {}
        self._routes_lock = Lock()

        self.rules_manager = RulesManager()

        self.init_rules_manager()

    def init_rules_manager(self) -> None:
        for rule in ALL_RULES:
            self.rules_manager.add_rule(rule)

    def handle(
        self, response: Response, client: Optional[ClientInfo] = None
    ) -> Union[Exception, bool]:
        """
        Handle an incoming message with full routing logic.

        Returns True if handled successfully, Exception on unexpected error.
        """
        try:
            ctx = MessageContext(response, self, client, self.is_server)
            self.rules_manager.process(ctx)
        except Exception as e:
            source = f"client {client.addr}" if (self.is_server and client) else "server"
            self.bus.emit(ErrorEvent.HANDLER, {"error": str(e), "source": source})
            self.bus.critical(f"Unexpected error handling message from {source}: {e}")
            return e

        return True

    def register(self, request_id: bytes) -> Queue:
        """
        Register a pending request BEFORE sending it.

        Avoids the race condition where the response arrives before the queue exists.
        """
        queue: Queue = Queue(maxsize=1)
        with self.pending_requests_lock:
            self.pending_requests[request_id] = queue
        self.bus.emit(
            MessageEvent.PENDING_REGISTERED,
            {
                "request_id": request_id.hex(),
            },
        )
        return queue

    def unregister(self, request_id: bytes) -> None:
        with self.pending_requests_lock:
            self.pending_requests.pop(request_id, None)

    def wait(self, request_id: bytes, timeout: float = 5.0) -> Optional[Response]:
        """
        Wait for a response matching request_id. Must be called after register().

        Returns the Response if received within timeout, None otherwise.
        """
        with self.pending_requests_lock:
            queue = self.pending_requests.get(request_id)

        if queue is None:
            self.bus.error(
                f"No registered request for id={request_id.hex()}. Call register() first."
            )
            return None

        try:
            return queue.get(timeout=timeout)  # type: ignore[no-any-return]
        except Empty:
            self.bus.emit(
                MessageEvent.PENDING_TIMEOUT,
                {
                    "request_id": request_id.hex(),
                    "timeout": timeout,
                },
            )
            self.bus.warning(
                f"Timeout waiting for response (id={request_id.hex()}) after {timeout}s"
            )
            return None
        finally:
            with self.pending_requests_lock:
                self.pending_requests.pop(request_id, None)

    def set_on_recv(self, callback: Callable) -> None:
        self.on_recv = callback  # type: ignore[assignment]

    def has_route(self, type_: MessageType) -> bool:
        with self._routes_lock:
            return type_ in self._routes

    def get_route(self, type_: MessageType) -> Optional[Callable]:
        with self._routes_lock:
            return self._routes.get(type_)

    def copy_routes(self) -> dict[MessageType, Callable]:
        with self._routes_lock:
            return dict(self._routes)

    def register_route(self, type_: MessageType, function: Callable) -> bool:
        with self._routes_lock:
            if type_ in self._routes:
                self.bus.warning(f"Route for type {type_} already registered — ignoring")
                return False
            self._routes[type_] = function
        self.bus.emit(
            MessageEvent.ROUTE_REGISTERED,
            {
                "type": type_,
                "name": type_.name,
            },
        )
        return True

    def unregister_route(self, type_: MessageType) -> bool:
        with self._routes_lock:
            if type_ not in self._routes:
                self.bus.warning(f"Route for type {type_} not registered — ignoring")
                return False
            self._routes.pop(type_)
        self.bus.emit(
            MessageEvent.ROUTE_UNREGISTERED,
            {
                "type": type_,
                "name": type_.name,
            },
        )
        return True

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)
