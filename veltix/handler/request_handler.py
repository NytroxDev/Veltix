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
from veltix.utils.mode import Mode


class RequestHandler:
    """
    Handles incoming message routing, correlation, and callback dispatch.

    This class centralizes all message handling logic including:
    - Automatic PING/PONG responses
    - Automatic HELLO/HELLO_ACK handshake (client side)
    - Request/response correlation for send_and_wait()
    - Callback routing per message type — executed in a thread pool
      so slow callbacks never block the recv loop

    Thread-safe for concurrent message handling.
    Works in both SERVER and CLIENT modes.
    """

    def __init__(self, sender: Sender, mode: Union[Mode, str], max_workers: int = 4):
        """
        Initialize the request handler.

        Args:
            sender: Sender instance for outgoing messages
            mode: Operation mode (Mode.SERVER or Mode.CLIENT)
            max_workers: Number of worker threads for callback execution (default: 4)
        """
        self.on_recv = None
        self.mode = mode
        self.is_server = self.mode == Mode.SERVER

        self._logger = Logger.get_instance()
        self._logger.trace(f"RequestHandler initialized in {mode} mode")

        self.sender = sender

        # Handshake handler — created once, used for HELLO/HELLO_ACK routing
        self.handshake_handler = HandshakeHandler(sender=sender, mode=mode)

        # Callback executor — runs on_recv in a thread pool
        self._executor = CallbackExecutor(max_workers=max_workers)

        # Pending requests waiting for responses (request_id -> Queue)
        self.pending_requests: dict[str, Queue] = {}
        self.pending_requests_lock = Lock()

        self._logger.debug("RequestHandler ready to handle messages")

    def handle(self, response: Response, client=None) -> Union[Exception, bool]:
        """
        Handle an incoming message with full routing logic.

        Processing order:
        1. Auto-respond to PING messages
        2. Auto-handle HELLO (client side only) — respond with HELLO_ACK
        3. Deliver to pending request if waiting (send_and_wait / HELLO_ACK on server)
        4. Submit on_recv callback to the executor (non-blocking)

        Args:
            response: Incoming response to handle
            client: ClientInfo if SERVER mode, None if CLIENT mode

        Returns:
            True if handled successfully, Exception if error occurred
        """
        try:
            source = f"client {client.addr}" if self.is_server else "server"
            self._logger.trace(f"Handling message type {response.type.name} from {source}")

            # Auto-respond to PING
            if response.type == PING:
                self._logger.debug(f"Received PING from {source}, auto-responding with PONG")
                pong_request = Request(PONG, b"", request_id=response.request_id)

                if self.is_server:
                    self.sender.send(pong_request, client=client.conn)
                else:
                    self.sender.send(pong_request)

                self._logger.debug(f"Auto-responded with PONG to {source}")
                return True

            # Auto-handle HELLO (client side only)
            if response.type == HELLO and not self.is_server:
                self._logger.debug("Received HELLO from server, auto-responding with HELLO_ACK")

                ok = self.handshake_handler.handle_hello(response)
                if ok:
                    self.handshake_handler.send_hello_ack(response.request_id)
                else:
                    self._logger.warning("[Handshake] HELLO invalid — dropping connection")

                return True

            # Check if someone is waiting for this response (send_and_wait)
            with self.pending_requests_lock:
                is_pending = response.request_id in self.pending_requests
                if is_pending:
                    queue = self.pending_requests[response.request_id]
                    self._logger.trace(f"Response {response.request_id} matches pending request")

            if is_pending:
                queue.put(response)
                self._logger.debug(f"Delivered response {response.request_id} to waiting request")
            else:
                if self.on_recv:
                    self._logger.trace(f"Submitting on_recv callback for {source}")
                    if self.is_server:
                        self._executor.submit(self.on_recv, client, response)
                    else:
                        self._executor.submit(self.on_recv, response)
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
        where the response arrives before the queue is registered.

        Args:
            request_id: Unique request identifier to register

        Returns:
            Queue instance that will receive the response
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
            request_id: Unique request identifier to unregister
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
            request_id: Unique request identifier to wait for
            timeout: Maximum time to wait in seconds (default: 5.0)

        Returns:
            Response object if received within timeout, None otherwise
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

    def set_on_recv(self, callback: Callable):
        """
        Set the default callback for all unhandled messages.

        Args:
            callback: Function to call for incoming messages
                     - SERVER mode signature: callback(client: ClientInfo, response: Response)
                     - CLIENT mode signature: callback(response: Response)
        """
        self.on_recv = callback
        self._logger.debug("Default on_recv callback registered")

    def shutdown(self) -> None:
        """
        Shutdown the executor gracefully.

        Should be called when the server/client is shutting down.
        """
        self._executor.shutdown()
