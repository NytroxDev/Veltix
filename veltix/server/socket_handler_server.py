from __future__ import annotations

import time
from typing import Callable, Optional, Dict, List

from veltix.network.network_handler import VxCore
from veltix.network.requests_handler import Langage, Requests, Sender


class RequestsSize:
    TINY = 512
    SMALL = 2048
    MEDIUM = 4096
    LARGE = 8192
    HUGE = 16384


class TempClient:
    """Client temporaire avant authentification"""

    def __init__(self, sock, addr, server: Server):
        self.sock = sock
        self.addr = addr
        self.server = server
        self.running = True
        self._buffer = bytearray()

    def _handle_data(self, data: memoryview):
        """Appelé par le core quand des données arrivent"""
        self._buffer.extend(data)
        # Essayer de décoder
        try:
            payload = Requests.decode(bytes(self._buffer), self.server.langage)
            self._buffer.clear()
            if self.server._on_message:
                self.server._on_message(self, payload)
        except Exception:
            # Pas encore assez de données ou erreur
            if len(self._buffer) > self.server.recv_buffer * 2:
                # Buffer trop gros, probablement invalide
                if self.server._on_invalid_request:
                    self.server._on_invalid_request(self, bytes(self._buffer))
                self.close()

    def send(self, payload: Requests):
        """Envoie une requête"""
        data = payload.encode()
        if self.server.core:
            self.server.core.send(self.sock, data)

    def recv(self, timeout=None):
        """Réception synchrone bloquante (pour compatibilité)"""
        self.sock.settimeout(timeout)
        try:
            data = self.sock.recv(self.server.recv_buffer)
            return Requests.decode(data, self.server.langage)
        except:
            return None

    def is_auth(self, payload: dict):
        """Upgrade vers Client authentifié"""
        new_client = Client(self.sock, self.addr, self.server, payload)
        self.server._upgrade_client(self, new_client)
        if self.server._on_auth:
            self.server._on_auth(new_client)
        return new_client

    def ban(self, duration, reason=""):
        """Ban l'IP du client"""
        ip = self.addr[0]
        expire = time.time() + duration
        self.server.banned[ip] = expire
        if self.server._on_ban:
            self.server._on_ban(self, duration, reason)
        self.close()

    def close(self):
        """Fermeture propre"""
        if not self.running:
            return
        self.running = False
        if self.server.core:
            self.server.core.close_socket(self.sock)
        if self in self.server.temp_clients:
            self.server.temp_clients.remove(self)


class Client:
    """Client authentifié avec accès complet"""

    def __init__(self, sock, addr, server: Server, payload=None):
        self.sock = sock
        self.addr = addr
        self.server = server
        self.running = True
        self._buffer = bytearray()
        self._payload = payload or {}

        # Sender pour l'historique et pre_send
        self.sender = Sender(
            lambda data: server.core.send(self.sock, data) if server.core else None,
            server.langage,
            server.size_history,
        )

        # Expose les attributs du payload
        for k, v in self._payload.items():
            setattr(self, k, v)

    def _handle_data(self, data: memoryview):
        """Appelé par le core quand des données arrivent"""
        self._buffer.extend(data)
        try:
            payload = Requests.decode(bytes(self._buffer), self.server.langage)
            self._buffer.clear()
            if self.server._on_message:
                self.server._on_message(self, payload)
        except Exception:
            if len(self._buffer) > self.server.recv_buffer * 2:
                if self.server._on_invalid_request:
                    self.server._on_invalid_request(self, bytes(self._buffer))
                self.close()

    def update_payload(self, payload: dict):
        """Met à jour le payload et les attributs"""
        self._payload.update(payload)
        for k, v in payload.items():
            setattr(self, k, v)
        if self.server._on_client_update:
            self.server._on_client_update(self, payload)

    def get(self, key, default=None):
        """Récupère une valeur du payload"""
        return self._payload.get(key, default)

    def set_pre_send_func(self, func: Callable):
        """Définit le callback pre-send"""
        self.sender.set_pre_send_callback(func)

    def send(self, payload: Requests):
        """Envoie via le Sender (avec historique)"""
        self.sender.send(payload)

    def recv(self, timeout=None):
        """Réception synchrone bloquante (pour compatibilité)"""
        self.sock.settimeout(timeout)
        try:
            data = self.sock.recv(self.server.recv_buffer)
            return Requests.decode(data, self.server.langage)
        except:
            return None

    def ban(self, duration, reason=""):
        """Ban l'IP du client"""
        ip = self.addr[0]
        expire = time.time() + duration
        self.server.banned[ip] = expire
        if self.server._on_ban:
            self.server._on_ban(self, duration, reason)
        self.close()

    def close(self):
        """Fermeture propre"""
        if not self.running:
            return
        self.running = False
        if self.server.core:
            self.server.core.close_socket(self.sock)
        if self in self.server.clients:
            self.server.clients.remove(self)


class Server:
    """Serveur haute performance avec API simple"""

    def __init__(
            self,
            langage: Langage,
            host="0.0.0.0",
            port=5050,
            size_history=50,
            recv_buffer=RequestsSize.MEDIUM,
            max_conn_per_ip=100,
    ):
        self.host = host
        self.port = port
        self.recv_buffer = recv_buffer
        self.size_history = size_history
        self.langage = langage
        self.running = False

        # Stockage clients
        self.temp_clients: List[TempClient] = []
        self.clients: List[Client] = []
        self.banned: Dict[str, float] = {}

        # Mapping sock -> client object
        self._sock_to_client: Dict = {}

        # Core réseau optimisé
        self.core = VxCore(recv_bufsize=recv_buffer)
        self.core.max_conn_per_ip = max_conn_per_ip

        # Callbacks privés
        self._on_connect: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None
        self._on_message: Optional[Callable] = None
        self._on_auth: Optional[Callable] = None
        self._on_ban: Optional[Callable] = None
        self._on_unban: Optional[Callable] = None
        self._on_invalid_request: Optional[Callable] = None
        self._on_client_update: Optional[Callable] = None

        # Setup des callbacks du core
        self.core.on_connect = self._core_on_connect
        self.core.on_data = self._core_on_data
        self.core.on_close = self._core_on_close

    # === Décorateurs pour binding simple ===
    def on_connect(self, func: Callable):
        """@server.on_connect"""
        self._on_connect = func
        return func

    def on_disconnect(self, func: Callable):
        """@server.on_disconnect"""
        self._on_disconnect = func
        return func

    def on_message(self, func: Callable):
        """@server.on_message"""
        self._on_message = func
        return func

    def on_auth(self, func: Callable):
        """@server.on_auth"""
        self._on_auth = func
        return func

    def on_ban(self, func: Callable):
        """@server.on_ban"""
        self._on_ban = func
        return func

    def on_unban(self, func: Callable):
        """@server.on_unban"""
        self._on_unban = func
        return func

    def on_invalid_request(self, func: Callable):
        """@server.on_invalid_request"""
        self._on_invalid_request = func
        return func

    def on_client_update(self, func: Callable):
        """@server.on_client_update"""
        self._on_client_update = func
        return func

    # === Callbacks internes du core ===
    def _core_on_connect(self, sock, addr):
        """Nouvelle connexion acceptée"""
        ip = addr[0]
        self.cleanup_ban()

        # Check ban
        if ip in self.banned and self.banned[ip] > time.time():
            self.core.close_socket(sock)
            return

        # Créer TempClient
        temp = TempClient(sock, addr, self)
        self.temp_clients.append(temp)
        self._sock_to_client[sock] = temp

        if self._on_connect:
            self._on_connect(temp)

    def _core_on_data(self, sock, data: memoryview):
        """Données reçues"""
        client = self._sock_to_client.get(sock)
        if client:
            client._handle_data(data)

    def _core_on_close(self, sock):
        """Connexion fermée"""
        client = self._sock_to_client.pop(sock, None)
        if client:
            client.running = False
            if isinstance(client, TempClient) and client in self.temp_clients:
                self.temp_clients.remove(client)
            elif isinstance(client, Client) and client in self.clients:
                self.clients.remove(client)

            if self._on_disconnect:
                self._on_disconnect(client)

    # === Méthodes publiques ===
    def start(self):
        """Démarre le serveur (non-bloquant)"""
        self.core.start_server(self.host, self.port)
        self.running = True
        print(f"[+] Serveur démarré sur {self.host}:{self.port}")

    def run_forever(self):
        """Démarre et bloque sur la boucle réseau"""
        self.start()
        self.core.run_forever()

    def cleanup_ban(self):
        """Nettoie les bans expirés"""
        now = time.time()
        self.banned = {ip: exp for ip, exp in self.banned.items() if exp > now}

    def _upgrade_client(self, temp_client: TempClient, new_client: Client):
        """Upgrade TempClient -> Client"""
        if temp_client in self.temp_clients:
            self.temp_clients.remove(temp_client)
        self.clients.append(new_client)
        self._sock_to_client[new_client.sock] = new_client
        print(f"[+] Client {new_client.addr} authentifié")

    def get_all_connection(self):
        """Retourne tous les clients authentifiés"""
        return self.clients

    def count_connection(self):
        """Compte les clients authentifiés"""
        return len(self.clients)

    def send_all(self, payload: Requests):
        """Envoie à tous les clients authentifiés"""
        for c in self.clients:
            c.send(payload)

    def get_stats(self):
        """Statistiques du serveur"""
        return {
            **self.core.get_stats(),
            'temp_clients': len(self.temp_clients),
            'auth_clients': len(self.clients),
            'banned_ips': len(self.banned)
        }

    def close(self):
        """Arrêt propre du serveur"""
        self.running = False
        self.core.stop()
        print("[x] Serveur arrêté")