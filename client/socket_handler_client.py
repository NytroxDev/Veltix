from __future__ import annotations
import socket
import threading
from typing import Callable, Optional

from network.requests_handler import Langage, Requests, Sender


class RequestsSize:
    TINY = 512
    SMALL = 2048
    MEDIUM = 4096
    LARGE = 8192
    HUGE = 16384


class ClientBinding:
    """Décorateurs pour binder les callbacks côté client."""
    def __init__(self, client: Client):
        self.client = client

    def on_connect(self, func: Callable):
        self.client._on_connect = func
        return func

    def on_disconnect(self, func: Callable):
        self.client._on_disconnect = func
        return func

    def on_message(self, func: Callable):
        self.client._on_message = func
        return func

    def on_auth(self, func: Callable):
        self.client._on_auth = func
        return func

    def on_ban(self, func: Callable):
        self.client._on_ban = func
        return func

    def on_unban(self, func: Callable):
        self.client._on_unban = func
        return func

    def on_invalid_request(self, func: Callable):
        self.client._on_invalid_request = func
        return func

    def on_client_update(self, func: Callable):
        self.client._on_client_update = func
        return func


class Client:
    def __init__(
        self,
        host: str,
        port: int,
        langage: Langage,
        recv_buffer: int = RequestsSize.MEDIUM,
        pre_send_func: Optional[Callable] = None
    ):
        self.host = host
        self.port = port
        self.langage = langage
        self.recv_buffer = recv_buffer
        self.pre_send_func = pre_send_func

        self.sock: Optional[socket.socket] = None
        self.running = False
        self.sender: Optional[Sender] = None

        # Payload du client (infos serveur ou perso)
        self._payload = {}

        # Events
        self._on_connect: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None
        self._on_message: Optional[Callable] = None
        self._on_auth: Optional[Callable] = None
        self._on_ban: Optional[Callable] = None
        self._on_unban: Optional[Callable] = None
        self._on_invalid_request: Optional[Callable] = None
        self._on_client_update: Optional[Callable] = None

        # Binding décorateur
        self.Binding = ClientBinding(self)

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.connect((self.host, self.port))
        self.sender = Sender(self.sock.sendall, self.langage, max_history=50, pre_send_callback=self.pre_send_func)
        self.running = True
        threading.Thread(target=self._listen_loop, daemon=True).start()
        if self._on_connect:
            self._on_connect(self)

    def _listen_loop(self):
        while self.running:
            try:
                data = self.sock.recv(self.recv_buffer) # type: ignore
                if not data:
                    break
                payload: Optional[Requests] = None
                try:
                    payload = Requests.decode(data=data, langage=self.langage)
                except Exception:
                    payload = None
                if payload and self._on_message:
                    self._on_message(self, payload)
            except (ConnectionResetError, OSError):
                break
        self.close()

    def send(self, request: Requests):
        if self.sender:
            self.sender.send(request)

    def recv(self, timeout=None):
        if not self.sock:
            return None
        self.sock.settimeout(timeout)
        try:
            data = self.sock.recv(self.recv_buffer)
            return Requests.decode(data, self.langage)
        except:
            return None

    def set_pre_send_func(self, func: Callable):
        self.pre_send_func = func
        if self.sender:
            self.sender.set_pre_send_callback(func)

    def close(self):
        if not self.running:
            return
        self.running = False
        try:
            if self.sock:
                self.sock.close()
        except:
            pass
        if self._on_disconnect:
            self._on_disconnect(self)

    # Payload helpers
    def update_payload(self, payload: dict):
        self._payload.update(payload)
        if self._on_client_update:
            self._on_client_update(self, payload)

    def get(self, key, default=None):
        return self._payload.get(key, default)
