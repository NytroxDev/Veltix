from __future__ import annotations

import threading
from typing import Callable, Optional

from veltix.network.network_handler import VxCore
from veltix.network.requests_handler import Langage, Requests, Sender


class RequestsSize:
    TINY = 512
    SMALL = 2048
    MEDIUM = 4096
    LARGE = 8192
    HUGE = 16384


class Client:
    """Client haute performance avec reconnexion automatique"""

    def __init__(
            self,
            host: str,
            port: int,
            langage: Langage,
            recv_buffer: int = RequestsSize.MEDIUM,
            pre_send_func: Optional[Callable] = None,
            auto_reconnect: bool = False,
            reconnect_delay: float = 2.0
    ):
        self.host = host
        self.port = port
        self.langage = langage
        self.recv_buffer = recv_buffer
        self.pre_send_func = pre_send_func
        self.auto_reconnect = auto_reconnect
        self.reconnect_delay = reconnect_delay

        self.sock = None
        self.running = False
        self.connected = False
        self.sender: Optional[Sender] = None
        self._buffer = bytearray()

        # Payload du client (infos serveur ou perso)
        self._payload = {}

        # Core réseau
        self.core = VxCore(
            recv_bufsize=recv_buffer,
            bufpool_size=512,
            conn_timeout=60.0
        )

        # Setup callbacks du core
        self.core.on_connect = self._core_on_connect
        self.core.on_data = self._core_on_data
        self.core.on_close = self._core_on_close

        # Events publics
        self._on_connect: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None
        self._on_message: Optional[Callable] = None
        self._on_auth: Optional[Callable] = None
        self._on_ban: Optional[Callable] = None
        self._on_unban: Optional[Callable] = None
        self._on_invalid_request: Optional[Callable] = None
        self._on_client_update: Optional[Callable] = None

    # === Décorateurs pour binding ===
    def on_connect(self, func: Callable):
        """@client.on_connect"""
        self._on_connect = func
        return func

    def on_disconnect(self, func: Callable):
        """@client.on_disconnect"""
        self._on_disconnect = func
        return func

    def on_message(self, func: Callable):
        """@client.on_message"""
        self._on_message = func
        return func

    def on_auth(self, func: Callable):
        """@client.on_auth"""
        self._on_auth = func
        return func

    def on_ban(self, func: Callable):
        """@client.on_ban"""
        self._on_ban = func
        return func

    def on_unban(self, func: Callable):
        """@client.on_unban"""
        self._on_unban = func
        return func

    def on_invalid_request(self, func: Callable):
        """@client.on_invalid_request"""
        self._on_invalid_request = func
        return func

    def on_client_update(self, func: Callable):
        """@client.on_client_update"""
        self._on_client_update = func
        return func

    # === Callbacks internes du core ===
    def _core_on_connect(self, sock):
        """Connexion établie"""
        self.connected = True
        self.sock = sock

        # Créer le sender
        self.sender = Sender(
            lambda data: self.core.send(self.sock, data) if self.core and self.sock else None,
            self.langage,
            pre_send_callback=self.pre_send_func
        )

        if self._on_connect:
            self._on_connect(self)

    def _core_on_data(self, data: memoryview):
        """Données reçues"""
        self._buffer.extend(data)

        # Essayer de décoder
        try:
            payload = Requests.decode(bytes(self._buffer), self.langage)
            self._buffer.clear()

            if self._on_message:
                self._on_message(self, payload)
        except Exception:
            # Pas encore assez de données ou erreur
            if len(self._buffer) > self.recv_buffer * 2:
                # Buffer trop gros, probablement invalide
                if self._on_invalid_request:
                    self._on_invalid_request(self, bytes(self._buffer))
                self._buffer.clear()
                self.close()

    def _core_on_close(self, ):
        """Connexion fermée"""
        self.connected = False
        self.sock = None

        if self._on_disconnect:
            self._on_disconnect(self)

        # Reconnexion auto
        if self.auto_reconnect and self.running:
            threading.Timer(self.reconnect_delay, self._try_reconnect).start()

    def _try_reconnect(self):
        """Tentative de reconnexion"""
        if self.running and not self.connected:
            try:
                self.sock = self.core.connect(self.host, self.port)
            except Exception:
                # Retry plus tard
                if self.running:
                    threading.Timer(self.reconnect_delay, self._try_reconnect).start()

    # === Méthodes publiques ===
    def connect(self):
        """Connexion au serveur (non-bloquant)"""
        self.running = True
        self.sock = self.core.connect(self.host, self.port)

        # Lancer la boucle réseau dans un thread
        threading.Thread(target=self.core.run_forever, daemon=True).start()

    def send(self, request: Requests):
        """Envoie une requête"""
        if self.sender and self.connected:
            self.sender.send(request)

    def recv(self, timeout=None):
        """Réception synchrone bloquante (pour compatibilité)"""
        if not self.sock:
            return None
        self.sock.settimeout(timeout)
        try:
            data = self.sock.recv(self.recv_buffer)
            return Requests.decode(data, self.langage)
        except:
            return None

    def set_pre_send_func(self, func: Callable):
        """Définit le callback pre-send"""
        self.pre_send_func = func
        if self.sender:
            self.sender.set_pre_send_callback(func)

    def close(self):
        """Fermeture propre"""
        if not self.running:
            return
        self.running = False
        self.connected = False

        if self.sock and self.core:
            self.core.close_socket(self.sock)

        self.core.stop()

    # === Payload helpers ===
    def update_payload(self, payload: dict):
        """Met à jour le payload"""
        self._payload.update(payload)
        if self._on_client_update:
            self._on_client_update(self, payload)

    def get(self, key, default=None):
        """Récupère une valeur du payload"""
        return self._payload.get(key, default)

    def get_stats(self):
        """Statistiques du client"""
        return {
            **self.core.get_stats(),
            'connected': self.connected,
            'buffer_size': len(self._buffer)
        }
