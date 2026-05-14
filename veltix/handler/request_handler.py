"""Request handling and routing for incoming messages."""

from __future__ import annotations

from queue import Empty, Queue
from threading import Lock
from typing import TYPE_CHECKING, Callable, Optional, Union

from ..handler.callback_executor import CallbackExecutor
from ..handler.handshake_handler import HandshakeHandler
from ..internal.mode import Mode
from ..logger.core import Logger
from ..network.request import Request, Response
from ..network.system_types import HELLO, PING, PONG

if TYPE_CHECKING:
    from ..network.sender import Sender
    from ..network.types import MessageType


class RequestHandler:
    """
    Routes incoming messages, correlates request/response pairs, and dispatches callbacks.

    Processing order for each message:
    1. Auto-respond to PING with PONG
    2. Auto-handle HELLO (client side) — respond with HELLO_ACK
    3. Deliver to pending queue if send_and_wait() is waiting
    4. Dispatch to a registered route if one matches
    5. Fall back to default on_recv callback
    6. Log a warning if nothing handled the message
    """

    def __init__(self, mode: Union[Mode, str], max_workers: int = 4, sender: Sender = None) -> None:
        self.on_recv = None
        self.mode = mode
        self.is_server = self.mode == Mode.SERVER
        self.sender = sender

        self._logger = Logger.get_instance()
        self.handshake_handler = HandshakeHandler(sender=sender, mode=mode)
        self._executor = CallbackExecutor(max_workers=max_workers)

        self.pending_requests: dict[bytes, Queue] = {}
        self.pending_requests_lock = Lock()

        self._routes: dict[MessageType, Callable] = {}
        self.on_handshake_done: Optional[Callable] = None

    def handle(self, response: Response, client=None) -> Union[Exception, bool]:
        """
        Handle an incoming message with full routing logic.

        Returns True if handled successfully, Exception on unexpected error.
        """
        try:
            source = f"client {client.addr}" if self.is_server else "server"

            if response.type == PING:
                pong = Request(PONG, b"", request_id=response.request_id)
                self.sender.send(pong, client=client.conn) if self.is_server else self.sender.send(
                    pong
                )
                return True

            if response.type == HELLO and not self.is_server:
                ok = self.handshake_handler.handle_hello(response)
                if ok:
                    self.handshake_handler.send_hello_ack(response.request_id)
                    if self.on_handshake_done:
                        try:
                            self.on_handshake_done()
                        except Exception as e:
                            self._logger.error(f"Error in on_handshake_done: {e}")
                else:
                    self._logger.warning("[Handshake] HELLO invalid — dropping connection")
                return True

            with self.pending_requests_lock:
                is_pending = response.request_id in self.pending_requests
                if is_pending:
                    queue = self.pending_requests[response.request_id]
                    queue.put(response)
                    return True

            if response.type in self._routes:
                if self.is_server:
                    self._executor.submit(self._routes[response.type], response, client)
                else:
                    self._executor.submit(self._routes[response.type], response)
            elif self.on_recv:
                if self.is_server:
                    self._executor.submit(self.on_recv, client, response)
                else:
                    self._executor.submit(self.on_recv, response)
            else:
                self._logger.warning(f"No handler registered for message from {source}")

        except Exception as e:
            source = f"client {client.addr}" if (self.is_server and client) else "server"
            self._logger.critical(f"Unexpected error handling message from {source}: {e}")
            return e

        return True

    def register(self, request_id: bytes) -> Queue:
        """
        Register a pending request BEFORE sending it.

        Avoids the race condition where the response arrives before the queue exists.
        """
        queue = Queue(maxsize=1)
        with self.pending_requests_lock:
            self.pending_requests[request_id] = queue
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
            self._logger.error(
                f"No registered request for id={request_id.hex()}. Call register() first."
            )
            return None

        try:
            return queue.get(timeout=timeout)
        except Empty:
            self._logger.warning(
                f"Timeout waiting for response (id={request_id.hex()}) after {timeout}s"
            )
            return None
        finally:
            with self.pending_requests_lock:
                self.pending_requests.pop(request_id, None)

    def set_on_recv(self, callback: Callable) -> None:
        self.on_recv = callback

    def register_route(self, type_: MessageType, function: Callable) -> bool:
        if type_ in self._routes:
            self._logger.warning(f"Route for type {type_} already registered — ignoring")
            return False
        self._routes[type_] = function
        return True

    def unregister_route(self, type_: MessageType) -> bool:
        if type_ not in self._routes:
            self._logger.warning(f"Route for type {type_} not registered — ignoring")
            return False
        self._routes.pop(type_)
        return True

    def shutdown(self) -> None:
        self._executor.shutdown()
