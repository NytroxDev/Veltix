"""Request handling and routing for incoming messages."""

from collections.abc import Callable
from queue import Empty, Queue
from threading import Lock
from typing import Optional, Union

from veltix.logger.core import Logger
from veltix.network.request import Request, Response
from veltix.network.sender import Sender
from veltix.network.system_types import PING, PONG
from veltix.utils.mode import Mode


class RequestHandler:
    """
    Handles incoming message routing, correlation, and callback dispatch.

    This class centralizes all message handling logic including:
    - Automatic PING/PONG responses
    - Request/response correlation for send_and_wait()
    - Callback routing per message type

    Thread-safe for concurrent message handling.
    Works in both SERVER and CLIENT modes.
    """

    def __init__(self, sender: Sender, mode: Union[Mode, str]):
        """
        Initialize the request handler.

        Args:
            sender: Sender instance for outgoing messages
            mode: Operation mode (Mode.SERVER or Mode.CLIENT)
        """
        # Callback for unhandled messages
        self.on_recv = None

        # Store operation mode
        self.mode = mode

        # Cache server/client mode check for performance
        self.is_server = self.mode == Mode.SERVER

        # Logger instance
        self._logger = Logger.get_instance()
        self._logger.trace(f"RequestHandler initialized in {mode} mode")

        # Sender for outgoing messages
        self.sender = sender

        # Pending requests waiting for responses (request_id -> Queue)
        self._pending_requests: dict[str, Queue] = {}
        self._pending_requests_lock = Lock()

        self._logger.debug("RequestHandler ready to handle messages")

    def handle(self, response: Response, client=None) -> Union[Exception, bool]:
        """
        Handle an incoming message with full routing logic.

        Processing order:
        1. Auto-respond to PING messages
        2. Deliver to pending request if waiting (send_and_wait)
        3. Call registered callback

        Args:
            response: Incoming response to handle
            client: ClientInfo if SERVER mode, None if CLIENT mode

        Returns:
            True if handled successfully, Exception if error occurred
        """
        try:
            # Determine message source for logging
            source = f"client {client.addr}" if self.is_server else "server"
            self._logger.trace(f"Handling message type {response.type.name} from {source}")

            # Auto-respond to PING
            if response.type == PING:
                self._logger.debug(f"Received PING from {source}, auto-responding with PONG")

                # Create PONG response with matching request_id
                pong_request = Request(PONG, b"", request_id=response.request_id)

                # Send PONG based on mode
                if self.is_server:
                    # Server mode: send to specific client
                    self.sender.send(pong_request, client=client.conn)
                else:
                    # Client mode: send to server
                    self.sender.send(pong_request)

                self._logger.debug(f"Auto-responded with PONG to {source}")
                return True

            # Check if someone is waiting for this response (send_and_wait)
            with self._pending_requests_lock:
                is_pending = response.request_id in self._pending_requests
                if is_pending:
                    queue = self._pending_requests[response.request_id]
                    self._logger.trace(f"Response {response.request_id} matches pending request")

            if is_pending:
                # Deliver response to waiting thread
                queue.put(response)
                self._logger.debug(f"Delivered response {response.request_id} to waiting request")
            else:
                # No one waiting, call normal callback
                if self.on_recv:
                    self._logger.trace(f"Dispatching to on_recv callback for {source}")
                    try:
                        # Callback signature differs based on mode
                        if self.is_server:
                            # Server mode: callback(client, response)
                            self.on_recv(client, response)
                        else:
                            # Client mode: callback(response) only
                            self.on_recv(response)

                        self._logger.debug(f"Called on_recv callback for {source}")
                    except Exception as e:
                        self._logger.error(
                            f"Error in on_recv callback for {source}: {type(e).__name__}: {e}"
                        )
                else:
                    self._logger.warning(f"No callback registered for message from {source}")

        except Exception as e:
            # Handle unexpected errors gracefully
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

        with self._pending_requests_lock:
            self._pending_requests[request_id] = queue
            self._logger.trace(f"Registered pending request {request_id}")

        return queue

    def unregister(self, request_id: str) -> None:
        """
        Unregister a pending request, discarding its queue.

        Should be called if the request could not be sent after register().

        Args:
            request_id: Unique request identifier to unregister
        """
        with self._pending_requests_lock:
            self._pending_requests.pop(request_id, None)
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

        with self._pending_requests_lock:
            queue = self._pending_requests.get(request_id)

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
            with self._pending_requests_lock:
                if request_id in self._pending_requests:
                    del self._pending_requests[request_id]
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
