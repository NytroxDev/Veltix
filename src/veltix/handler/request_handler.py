"""Request handling and routing for incoming messages."""

from __future__ import annotations

import inspect
from queue import Empty, Queue
from threading import Lock
from typing import TYPE_CHECKING, Any

from ..handler.callback_executor import CallbackExecutor
from ..handler.handshake_handler import HandshakeHandler
from ..internal.events import ErrorEvent, MessageEvent
from ..internal.mode import Mode
from .rules import ALL_RULES
from .rules_manager import MessageContext, RulesManager

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..internal.bus import VeltixBus
    from ..network.response import Response
    from ..network.sender import Sender
    from ..network.types import MessageType
    from ..server.client_info import ClientInfo


def validate_callback_signature(
    callback: Callable,
    *,
    label: str,
    expected: int,
    dispatched: str,
    fix_sig: str,
    target: str | None = None,
) -> None:
    """Check that a callback can accept its dispatched arguments.

    Server routes and callbacks are dispatched with ``(client, response)``
    (or ``(client)`` for connect/disconnect), client callbacks with
    ``(response)`` / ``(state)`` / none. A mismatched signature used to fail
    lazily inside the callback thread pool with a generic ``TypeError``; now
    it fails at registration with a message that shows the expected signature.

    Args:
        callback: The function or callable being registered.
        label: Short description used in the error (e.g. "Route handler").
        expected: Number of positional arguments dispatched at call time.
        dispatched: Argument list shown in the error (e.g. "client, response").
        fix_sig: Recommended parameter list for the fix message.
        target: Optional scope shown after the name (e.g. a message type name).

    Raises:
        TypeError: If the callback cannot accept the dispatched arguments.
    """
    try:
        sig = inspect.signature(callback)
    except (TypeError, ValueError):
        return  # uninspectable callable: let the runtime decide

    params = list(sig.parameters.values())
    if any(
        p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD) for p in params
    ):
        return  # *args/**kwargs absorb the dispatched arguments

    positional = [
        p
        for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    required = sum(1 for p in positional if p.default is inspect.Parameter.empty)
    max_pos = len(positional)
    kwonly_required = any(
        p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is inspect.Parameter.empty
        for p in params
    )

    if required <= expected <= max_pos and not kwonly_required:
        return

    name = getattr(callback, "__name__", type(callback).__name__)
    target_hint = f" for '{target}'" if target else ""
    span = str(required) if required == max_pos else f"{required}-{max_pos}"
    kw_hint = " and missing keyword-only arguments" if kwonly_required else ""
    raise TypeError(
        f"{label} '{name}'{target_hint} cannot be called with ({dispatched}): "
        f"its signature accepts {span} positional argument(s){kw_hint}. "
        f"Fix: def {name}({fix_sig}) -> None."
    )


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
        mode: Mode | str,
        bus: VeltixBus,
        max_workers: int = 4,
        sender: Sender | None = None,
    ) -> None:
        if isinstance(mode, str):
            mode = Mode(mode)
        self.bus = bus
        self.on_recv: Callable[..., Any] | None = None
        self.mode = mode
        self.is_server = self.mode == Mode.SERVER
        self.sender = sender

        self.handshake_handler = HandshakeHandler(mode=mode, bus=self.bus)
        self._executor = CallbackExecutor(max_workers=max_workers, bus=self.bus)

        self.pending_requests: dict[int, Queue[Response]] = {}
        self.pending_requests_lock = Lock()

        self._routes: dict[MessageType, Callable] = {}
        self._routes_lock = Lock()

        self.rules_manager = RulesManager()

        self.init_rules_manager()

    def init_rules_manager(self) -> None:
        for rule_cls in ALL_RULES:
            self.rules_manager.add_rule(rule_cls())

    def handle(self, response: Response, client: ClientInfo | None = None) -> bool:
        """Handle an incoming message with full routing logic.

        Args:
            response: The received message.
            client: The sending client (server-side only).

        Returns:
            True if the message was handled successfully, False on error.
        """
        try:
            ctx = MessageContext(response, self, client, self.is_server)
            self.rules_manager.process(ctx)
        except Exception as e:
            source = f"client {client.addr}" if (self.is_server and client) else "server"
            self.bus.emit(ErrorEvent.HANDLER, {"error": str(e), "source": source})
            self.bus.critical(f"Unexpected error handling message from {source}: {e}")
            return False

        return True

    def register(self, request_id: int) -> Queue[Response]:
        """
        Register a pending request BEFORE sending it.

        Avoids the race condition where the response arrives before the queue exists.
        """
        queue: Queue[Response] = Queue(maxsize=1)
        with self.pending_requests_lock:
            self.pending_requests[request_id] = queue
        self.bus.emit(
            MessageEvent.PENDING_REGISTERED,
            {
                "request_id": request_id,
            },
        )
        return queue

    def unregister(self, request_id: int) -> None:
        with self.pending_requests_lock:
            self.pending_requests.pop(request_id, None)

    def wait(self, request_id: int, timeout: float = 5.0) -> Response | None:
        """
        Wait for a response matching request_id. Must be called after register().

        Returns the Response if received within timeout, None otherwise.
        """
        with self.pending_requests_lock:
            queue = self.pending_requests.get(request_id)

        if queue is None:
            self.bus.error(f"No registered request for id={request_id}. Call register() first.")
            return None

        try:
            return queue.get(timeout=timeout)
        except Empty:
            self.bus.emit(
                MessageEvent.PENDING_TIMEOUT,
                {
                    "request_id": request_id,
                    "timeout": timeout,
                },
            )
            self.bus.warning(f"Timeout waiting for response (id={request_id}) after {timeout}s")
            return None
        finally:
            with self.pending_requests_lock:
                self.pending_requests.pop(request_id, None)

    def set_on_recv(self, callback: Callable[..., Any]) -> None:
        if self.mode is Mode.SERVER:
            validate_callback_signature(
                callback,
                label="on_recv callback",
                expected=2,
                dispatched="client, response",
                fix_sig="client: ClientInfo, response: Response",
            )
        else:
            validate_callback_signature(
                callback,
                label="on_recv callback",
                expected=1,
                dispatched="response",
                fix_sig="response: Response",
            )
        self.on_recv = callback

    def has_route(self, type_: MessageType) -> bool:
        with self._routes_lock:
            return type_ in self._routes

    def get_route(self, type_: MessageType) -> Callable | None:
        with self._routes_lock:
            return self._routes.get(type_)

    def copy_routes(self) -> dict[MessageType, Callable]:
        with self._routes_lock:
            return dict(self._routes)

    def register_route(self, type_: MessageType, function: Callable) -> bool:
        with self._routes_lock:
            if type_ in self._routes:
                self.bus.warning(f"Route for type {type_} already registered - ignoring")
                return False
            self._validate_route(type_, function)
            self._routes[type_] = function
        self.bus.emit(
            MessageEvent.ROUTE_REGISTERED,
            {
                "type": type_,
                "name": type_.name,
            },
        )
        return True

    def _validate_route(self, type_: MessageType, function: Callable) -> None:
        """Check that a route handler can accept its dispatched arguments.

        Server routes are called with ``(client, response)``, client routes
        with ``(response)``. A mismatched signature used to fail lazily inside
        the callback thread pool with a generic ``TypeError``; now it fails
        fast at registration with a message that shows the expected signature.

        Args:
            type_: The message type being registered.
            function: The route handler.

        Raises:
            TypeError: If the handler cannot accept the dispatched arguments.
        """
        if self.mode is Mode.SERVER:
            validate_callback_signature(
                function,
                label="Route handler",
                expected=2,
                dispatched="client, response",
                fix_sig="client: ClientInfo, response: Response",
                target=type_.name,
            )
        else:
            validate_callback_signature(
                function,
                label="Route handler",
                expected=1,
                dispatched="response",
                fix_sig="response: Response",
                target=type_.name,
            )

    def unregister_route(self, type_: MessageType) -> bool:
        with self._routes_lock:
            if type_ not in self._routes:
                self.bus.warning(f"Route for type {type_} not registered - ignoring")
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
