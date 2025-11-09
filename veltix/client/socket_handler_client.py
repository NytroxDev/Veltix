from __future__ import annotations

import threading
from typing import Callable, Optional

from veltix.crypto.crypto_handler import (
    generate_x25519_key,
    trade_keys_chacha20,
    encrypt_chacha20,
    decrypt_chacha20,
    generate_private_sign,
    sign,
    verify_sign
)
from veltix.network.network_handler import VxCore
from veltix.network.requests_handler import Langage, Requests, Sender


class RequestsSize:
    TINY = 512
    SMALL = 2048
    MEDIUM = 4096
    LARGE = 8192
    HUGE = 16384

class Client:
    """Client haute performance avec crypto automatique"""

    def __init__(
            self,
            host: str,
            port: int,
            langage: Langage,
            recv_buffer: int = RequestsSize.MEDIUM,
            auto_reconnect: bool = False,
            reconnect_delay: float = 2.0
    ):
        self.host = host
        self.port = port
        self.langage = langage
        self.recv_buffer = recv_buffer
        self.auto_reconnect = auto_reconnect
        self.reconnect_delay = reconnect_delay

        self.sock = None
        self.running = False
        self.connected = False
        self.sender: Optional[Sender] = None
        self._buffer = bytearray()
        self._payload = {}

        # Core réseau
        self.core = VxCore(
            recv_bufsize=recv_buffer,
            bufpool_size=512,
            conn_timeout=60.0
        )
        self.core.on_connect = self._core_on_connect
        self.core.on_data = self._core_on_data
        self.core.on_close = self._core_on_close

        # Callbacks
        self._on_connect: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None
        self._on_message: Optional[Callable] = None

        # Crypto auto
        self._x25519_priv, self._x25519_pub = generate_x25519_key()
        self._chacha: Optional = None
        self._signer_priv, self._signer_pub = generate_private_sign(path="keys")  # sauvegarde automatique

    # === Décorateurs ===
    def on_connect(self, func: Callable):
        self._on_connect = func
        return func

    def on_disconnect(self, func: Callable):
        self._on_disconnect = func
        return func

    def on_message(self, func: Callable):
        self._on_message = func
        return func

    # === Core callbacks ===
    def _core_on_connect(self, sock):
        self.connected = True
        self.sock = sock

        # Sender avec crypto automatique
        self.sender = Sender(
            lambda data: self.core.send(self.sock, data) if self.core and self.sock else None,
            self.langage
        )
        self.sender.set_encrypt_func(lambda b: encrypt_chacha20(self._chacha, b) if self._chacha else b)

        # Envoi handshake automatique (pub key X25519 + signature)
        handshake_data = {
            "x25519_pub": self._x25519_pub.hex(),
            "signature": sign(self._signer_priv, self._x25519_pub)
        }
        handshake_req = Requests("0001", handshake_data, self.langage)
        self.sender.send(handshake_req, private=True)

        if self._on_connect:
            self._on_connect(self)

    def _core_on_data(self, data: memoryview):
        self._buffer.extend(data)
        try:
            raw_bytes = bytes(self._buffer)
            if self._chacha:
                raw_bytes = decrypt_chacha20(self._chacha, raw_bytes)
            payload = Requests.decode(raw_bytes, self.langage)

            # Si payload handshake du peer, on calcule la clé ChaCha20
            if payload.type == "0002" and "x25519_pub" in payload.content:
                peer_pub = bytes.fromhex(payload.content["x25519_pub"])
                self._chacha = trade_keys_chacha20(self._x25519_priv, peer_pub)

                # On peut vérifier la signature si besoin
                verify_sign(self._signer_pub, peer_pub, payload.content["signature"])

            self._buffer.clear()
            if self._on_message:
                self._on_message(self, payload)
        except Exception:
            if len(self._buffer) > self.recv_buffer * 2:
                self._buffer.clear()
                self.close()

    def _core_on_close(self):
        self.connected = False
        self.sock = None
        if self.auto_reconnect and self.running:
            threading.Timer(self.reconnect_delay, self._try_reconnect).start()
        if self._on_disconnect:
            self._on_disconnect(self)

    def _try_reconnect(self):
        if self.running and not self.connected:
            try:
                self.sock = self.core.connect(self.host, self.port)
            except Exception:
                threading.Timer(self.reconnect_delay, self._try_reconnect).start()

    # === Méthodes publiques ===
    def connect(self):
        self.running = True
        self.sock = self.core.connect(self.host, self.port)
        threading.Thread(target=self.core.run_forever, daemon=True).start()

    def send(self, request: Requests):
        if self.sender and self.connected:
            self.sender.send(request)

    def close(self):
        self.running = False
        self.connected = False
        if self.sock and self.core:
            self.core.close_socket(self.sock)
        self.core.stop()
