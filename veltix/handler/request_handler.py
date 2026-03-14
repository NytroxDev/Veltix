"""Request handling and routing for incoming messages."""

from collections.abc import Callable
from queue import Empty, Queue
from threading import Lock
from typing import Optional, Union

from veltix.handler.callback_executor import CallbackExecutor
from veltix.handler.handshake_handler import HandshakeHandler
from veltix.logger.core import Logger
from veltix.network.request import Request, Response
from veltix.network.sender import Sender
from veltix.network.system_types import HELLO, PING, PONG
from veltix.network.types import MessageType
from veltix.internal.mode import Mode


class RequestHandler:
    """
    Handles incoming message routing, correlation, and callback dispatch.

    This class centralizes all message handling logic including:
    - Automatic PING/PONG responses
    - Automatic HELLO/HELLO_ACK handshake (client side)
    - Request/response correlation for send_and_wait()
    - Per-type route callbacks registered via register_route()
    - Default on_recv fallback for unrouted messages
    - All user callbacks are executed in a thread pool so slow
      handlers never block the recv loop

    Thread-safe for concurrent message handling.
    Works in both SERVER and CLIENT modes.
    """

    def __init__(self, sender: Sender, mode: Union[Mode, str], max_workers: int = 4):
        """
        Initialize the request handler.

        Args:
            sender:      Sender instance for outgoing messages.
            mode:        Operation mode (Mode.SERVER or Mode.CLIENT).
            max_workers: Number of worker threads for callback execution (default: 4).
        """
        self.on_recv = None
        self.mode = mode
        self.is_server = self.mode == Mode.SERVER

        self._logger = Logger.get_instance()
        self._logger.trace(f"RequestHandler initialized in {mode} mode")

        self.sender = sender

        # Handshake handler — created once, used for HELLO/HELLO_ACK routing
        self.handshake_handler = HandshakeHandler(sender=sender, mode=mode)

        # Callback executor — runs user callbacks in a thread pool
        self._executor = CallbackExecutor(max_workers=max_workers)

        # Pending requests waiting for a matching response (request_id → Queue)
        self.pending_requests: dict[str, Queue] = {}
        self.pending_requests_lock = Lock()

        # Per-type route callbacks registered via register_route()
        # Takes priority over on_recv for matching message types
        self._routes: dict[MessageType, Callable] = {}

        self._logger.debug("RequestHandler ready to handle messages")

    def handle(self, response: Response, client=None) -> Union[Exception, bool]:
        """
        Handle an incoming message with full routing logic.

        Processing order:
        1. Auto-respond to PING with PONG
        2. Auto-handle HELLO (client side only) — respond with HELLO_ACK
        3. Deliver to pending request queue if send_and_wait() is waiting
        4. Dispatch to a registered route if one matches the message type
        5. Fall back to the default on_recv callback
        6. Log a warning if nothing handled the message

        Args:
            response: Incoming response to handle.
            client:   ClientInfo if SERVER mode, None if CLIENT mode.

        Returns:
            True if handled successfully, Exception if an unexpected error occurred.
        """
        try:
            source = f"client {client.addr}" if self.is_server else "server"
            self._logger.trace(f"Handling message type {response.type.name} from {source}")

            # Step 1 — Auto-respond to PING
            if response.type == PING:
                self._logger.debug(f"Received PING from {source}, auto-responding with PONG")
                pong_request = Request(PONG, b"", request_id=response.request_id)

                if self.is_server:
                    self.sender.send(pong_request, client=client.conn)
                else:
                    self.sender.send(pong_request)

                self._logger.debug(f"Auto-responded with PONG to {source}")
                return True

            # Step 2 — Auto-handle HELLO (client side only)
            if response.type == HELLO and not self.is_server:
                self._logger.debug("Received HELLO from server, auto-responding with HELLO_ACK")

                ok = self.handshake_handler.handle_hello(response)
                if ok:
                    self.handshake_handler.send_hello_ack(response.request_id)
                else:
                    self._logger.warning("[Handshake] HELLO invalid — dropping connection")

                return True

            # Step 3 — Deliver to pending request if send_and_wait() is waiting
            with self.pending_requests_lock:
                is_pending = response.request_id in self.pending_requests
                if is_pending:
                    queue = self.pending_requests[response.request_id]
                    self._logger.trace(f"Response {response.request_id} matches pending request")

            if is_pending:
                queue.put(response)
                self._logger.debug(f"Delivered response {response.request_id} to waiting request")

            # Step 4 — Dispatch to registered route if one matches
            elif response.type in self._routes:
                self._logger.trace(f"Dispatching to route for type {response.type.name}")
                if self.is_server:
                    self._executor.submit(self._routes[response.type], response, client)
                else:
                    self._executor.submit(self._routes[response.type], response)

            # Step 5 — Fall back to default on_recv callback
            elif self.on_recv:
                self._logger.trace(f"Submitting on_recv callback for {source}")
                if self.is_server:
                    self._executor.submit(self.on_recv, client, response)
                else:
                    self._executor.submit(self.on_recv, response)

            # Step 6 — Nothing handled this message
            else:
                self._logger.warning(f"No callback registered for message from {source}")

        except Exception as e:
            source = f"client {client.addr}" if (self.is_server and client) else "server"
            self._logger.critical(f"Unexpected error handling message from {source}: {e}")
            return e
        else:
            return True

    def register(self, request_id: str) -> Queue:
        """
        Register a pending request before sending it.

        Must be called BEFORE sending the request to avoid race conditions
        where the response could arrive before the queue is registered.

        Args:
            request_id: Unique request identifier to register.

        Returns:
            Queue instance that will receive the matching response.
        """
        queue = Queue(maxsize=1)

        with self.pending_requests_lock:
            self.pending_requests[request_id] = queue
            self._logger.trace(f"Registered pending request {request_id}")

        return queue

    def unregister(self, request_id: str) -> None:
        """
        Unregister a pending request, discarding its queue.

        Args:
            request_id: Unique request identifier to unregister.
        """
        with self.pending_requests_lock:
            self.pending_requests.pop(request_id, None)
            self._logger.trace(f"Unregistered pending request {request_id}")

    def wait(self, request_id: str, timeout: float = 5.0) -> Optional[Response]:
        """
        Wait for a response matching the given request_id.

        Must be called after register() to ensure the queue exists.
        Automatically cleans up the pending request entry on completion
        or timeout.

        Args:
            request_id: Unique request identifier to wait for.
            timeout:    Maximum time to wait in seconds (default: 5.0).

        Returns:
            Matching Response if received within timeout, None otherwise.
        """
        self._logger.debug(f"Waiting for response {request_id} (timeout: {timeout}s)")

        with self.pending_requests_lock:
            queue = self.pending_requests.get(request_id)

        if queue is None:
            self._logger.error(
                f"No registered request found for {request_id}. "
                f"Did you call register() before wait()?"
            )
            return None

        try:
            response = queue.get(timeout=timeout)
            self._logger.debug(f"Received response for request {request_id}")
            return response
        except Empty:
            self._logger.warning(f"Timeout waiting for response {request_id} after {timeout}s")
            return None
        finally:
            with self.pending_requests_lock:
                if request_id in self.pending_requests:
                    del self.pending_requests[request_id]
                    self._logger.trace(f"Cleaned up pending request {request_id}")

    def set_on_recv(self, callback: Callable) -> None:
        """
        Set the default callback for all unrouted messages.

        Called for any message that has no matching registered route
        and is not awaited by send_and_wait().

        Args:
            callback: Function to call for incoming messages.
                      - SERVER mode: callback(client: ClientInfo, response: Response)
                      - CLIENT mode: callback(response: Response)
        """
        self.on_recv = callback
        self._logger.debug("Default on_recv callback registered")

    def register_route(self, type_: MessageType, function: Callable) -> bool:
        """
        Register a callback for a specific message type.

        Routed callbacks take priority over the default on_recv callback.
        The route callback is executed in the thread pool, just like on_recv,
        so slow handlers never block the recv loop.

        Args:
            type_:    Message type to intercept.
            function: Callback to invoke when a message of this type arrives.
                      Signature: callback(response: Response, client: ClientInfo | None)

        Returns:
            True if the route was registered, False if already registered.
        """
        self._logger.debug(f"Registering route for type {type_}")

        if type_ in self._routes:
            self._logger.warning(f"Route for type {type_} already registered — ignoring")
            return False

        self._routes[type_] = function
        return True

    def unregister_route(self, type_: MessageType) -> bool:
        """
        Unregister the callback for a specific message type.

        After unregistering, messages of this type will fall through
        to the default on_recv callback (or be dropped if none is set).

        Args:
            type_: Message type to unregister.

        Returns:
            True if the route was removed, False if it was not registered.
        """
        self._logger.debug(f"Unregistering route for type {type_}")

        if type_ not in self._routes:
            self._logger.warning(f"Route for type {type_} not registered — ignoring")
            return False

        self._routes.pop(type_)
        return True

    def shutdown(self) -> None:
        """
        Shutdown the executor gracefully.

        Should be called when the server or client is shutting down
        to allow in-progress callbacks to complete cleanly.
        """
        self._executor.shutdown()
