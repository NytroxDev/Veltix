from __future__ import annotations

import time
from typing import Callable, Optional, Dict

from veltix.crypto.ChaCha20_handler import ChaCha20Manager
from veltix.crypto.crypto_handler import (
    generate_x25519_key,
    sign,
    get_signer,
    decrypt_chacha20,
    encrypt_chacha20,
    trade_keys_chacha20,
)
from veltix.network.network_handler import VxCore
from veltix.network.requests_handler import Langage, Requests, Sender
from veltix.storage.storage_handler import VeltixStorage


# === Minimal request sizes (garde les tiens si besoin) ===
class RequestsSize:
    TINY = 512
    SMALL = 2048
    MEDIUM = 4096
    LARGE = 8192
    HUGE = 16384


# ---------------------
# TempClient (low mem)
# ---------------------
# noinspection PyProtectedMember
class TempClient:
    """
    Client temporaire avant authentification - ultra low memory.
    - handshake non bloquant : start_init() lance l'envoi INIT, réponse traitée dans _handle_data
    - buffers alloués lazy
    """

    __slots__ = (
        "sock",
        "addr",
        "server",
        "_chacha20",  # ChaCha20Manager ou None (créé seulement après handshake)
        "running",
        "initialised",
        "_recv_acc",  # lazy bytearray pour accrual des paquets incomplets
        "_xpriv",  # private x25519 (bytes) pendant handshake
        "_xpub",  # public x25519 (bytes) pendant handshake
        "_state",  # "init_sent", "waiting_peer", "ready", ...
    )

    def __init__(self, sock, addr, server: "Server"):
        self.sock = sock
        self.addr = addr
        self.server = server
        self._chacha20: Optional[ChaCha20Manager] = None
        self.running = True
        self.initialised = False
        self._recv_acc = None  # lazy allocate
        self._xpriv = None
        self._xpub = None
        self._state = None

    # --- Handshake: lancer non-bloquant ---
    def start_init(self):
        """
        Démarre le handshake sans bloquer : génère une paire x25519, signe la clé publique,
        et envoie la requête INIT. La réponse du pair sera traitée dans _handle_data.
        """
        # Génération de clé ephemeral (garde uniquement bytes; objets lourds non gardés)
        priv, pub = generate_x25519_key()  # retourne (priv, pub)
        self._xpriv = priv
        self._xpub = pub

        # signature
        signer = get_signer(self.server.get_signer_path())
        key_signed = sign(self._xpub, signer)

        # send INIT (non chiffré)
        req = Requests(self.server.langage.INIT, {"key_signed": key_signed}, self.server.langage)
        try:
            self.server.core.send(self.sock, req.encode())
        except Exception:
            # send failed -> close immediately
            self.close()
            return

        self._state = "init_sent"
        # on attend la réponse du pair via _handle_data

    # --- Internal receive handler (appelé par VxCore avec memoryview) ---
    def _handle_data(self, data: memoryview):
        """
        Appelé par le core quand des données arrivent.
        - si pas initialisé on accumule et on tente de parser (handshake)
        - si initialisé on déchiffre et on décode
        """
        # 1) Accumulate minimalement
        if self._recv_acc is None:
            # petite taille initiale (évite gros allocs souvent inutiles)
            self._recv_acc = bytearray(512)

        # append without creating new bytes objects
        if len(self._recv_acc) < self.server.recv_buffer * 2:
            self._recv_acc.extend(data)
        else:
            self.close()
            return

        # 2) Handshake state: si pas initialisé, on essaie de décoder la requête brute
        if not self.initialised:
            try:
                # decode requires bytes — on copy ici une seule fois quand il y a assez de données
                payload = Requests.decode(bytes(self._recv_acc), self.server.langage)
            except Exception:
                # message incomplet ou non-décodable pour l'instant;
                # protège contre accumulation infinie
                if len(self._recv_acc) > self.server.recv_buffer * 2:
                    if self.server._on_invalid_request:
                        self.server._on_invalid_request(self, bytes(self._recv_acc))
                    self.close()
                return

            # si on arrive ici, on a décodé une requête complète
            self._recv_acc.clear()

            # handshake: attente INIT du pair
            if payload.type == self.server.langage.INIT and self._state == "init_sent":
                peer_key = payload.content.get("key_signed")
                if peer_key:
                    # compute shared key and create ChaCha manager
                    try:
                        self._chacha20 = trade_keys_chacha20(self._xpriv, peer_key)
                    except Exception:
                        self.close()
                        return

                    self.initialised = True
                    self._state = "ready"

                    # appelle callback on_connect ou on_auth selon ton flow :
                    if self.server._on_connect:
                        # NOTE: on_connect receives a client-like object that is now secure
                        self.server._on_connect(self)
                    return

            # si on reçoit autre chose avant handshake terminé -> drop ou ban
            if self.server._on_invalid_request:
                self.server._on_invalid_request(self, bytes(self._recv_acc))
            # si tu veux, tu peux close() directement
            return

        # 3) Si initialisé : déchiffrer et dispatcher le message
        try:
            # data est la mémoire fournie par VxCore ; faire une copie minimale pour décryptage if nécessaire
            # decrypt_chacha20 s'attend probablement à bytes; on accepte la copie ici
            decrypted = decrypt_chacha20(self._chacha20, bytes(data))
            payload = Requests.decode(decrypted, self.server.langage)
            if self.server._on_message:
                self.server._on_message(self, payload)
        except Exception:
            # si erreur de parsing -> invalid request handling
            if self.server._on_invalid_request:
                try:
                    self.server._on_invalid_request(self, bytes(data))
                except Exception:
                    pass
            # tu peux décider de close ou non; ici on ne close pas immédiatement

    # --- send: si initialisé on chiffre, sinon envoi brut (handshake) ---
    def send(self, payload: Requests) -> bool:
        try:
            raw = payload.encode()
            if self.initialised and self._chacha20:
                out = encrypt_chacha20(self._chacha20, raw)
            else:
                out = raw
            return self.server.core.send(self.sock, out)
        except Exception:
            return False

    # --- recv synchrone minimal (garde mais déconseillé) ---
    def recv(self, timeout=None) -> Optional[Requests]:
        """
        Méthode de compatibilité synchronous. Eviter si possible (peut bloquer).
        Si utilisée, elle bloque sur sock.recv et doit être appelée en thread séparé.
        """
        self.sock.settimeout(timeout)
        try:
            if not self.initialised:
                return None
            data = self.sock.recv(self.server.recv_buffer)
            decrypted = decrypt_chacha20(self._chacha20, data)
            return Requests.decode(decrypted, self.server.langage)
        except Exception:
            return None

    def is_auth(self, payload: dict):
        """Upgrade vers ServerClient (authentifié)."""
        new_client = ServerClient(self.sock, self.addr, self.server, payload)
        self.server._upgrade_client(self, new_client)
        if self.server._on_auth:
            self.server._on_auth(new_client)
        return new_client

    def ban(self, duration, reason=""):
        ip = self.addr[0]
        expire = time.time() + duration
        self.server.banned[ip] = expire
        if self.server._on_ban:
            self.server._on_ban(self, duration, reason)
        self.close()

    def close(self):
        if not self.running:
            return
        self.running = False
        # demander au core de fermer proprement (libère recv_buf dans BufferPool)
        if self.server.core:
            self.server.core.close_socket(self.sock)
        # nettoie references légères
        if self in self.server.temp_clients:
            try:
                self.server.temp_clients.remove(self)
            except ValueError:
                pass


# ---------------------
# ServerClient (low mem)
# ---------------------
# noinspection PyProtectedMember
class ServerClient:
    """
    Client authentifié - ultra low memory.
    - __slots__ pour faible empreinte
    - buffer lazy + sender lazy
    """

    __slots__ = (
        "sock",
        "addr",
        "server",
        "running",
        "_recv_acc",
        "_payload",
        "_sender",  # lazy: instancier seulement si on envoie souvent / historique
    )

    def __init__(self, sock, addr, server: "Server", payload=None):
        self.sock = sock
        self.addr = addr
        self.server = server
        self.running = True
        self._recv_acc = None
        self._payload = payload or {}
        self._sender = None  # créer sur demande

    # handle data : utilise memoryview fourni par core
    def _handle_data(self, data: memoryview):
        if self._recv_acc is None:
            self._recv_acc = bytearray(256)  # petit buffer initial

        if len(self._recv_acc) < self.server.recv_buffer * 2:
            self._recv_acc.extend(data)
        else:
            self.close()
            return

        try:
            payload = Requests.decode(bytes(self._recv_acc), self.server.langage)
            self._recv_acc.clear()
            if self.server._on_message:
                self.server._on_message(self, payload)
        except Exception:
            if len(self._recv_acc) > self.server.recv_buffer * 2:
                if self.server._on_invalid_request:
                    self.server._on_invalid_request(self, bytes(self._recv_acc))
                self.close()

    # lazy sender creation
    def _ensure_sender(self):
        if self._sender is None:
            self._sender = Sender(
                lambda d: self.server.core.send(self.sock, d) if self.server.core else None,
                self.server.langage,
                self.server.size_history,
            )

    def update_payload(self, payload: dict):
        self._payload.update(payload)
        for k, v in payload.items():
            setattr(self, k, v)
        if self.server._on_client_update:
            self.server._on_client_update(self, payload)

    def get(self, key, default=None):
        return self._payload.get(key, default)

    def set_pre_send_func(self, func: Callable):
        self._ensure_sender()
        self._sender.set_pre_send_callback(func)

    def send(self, payload: Requests):
        self._ensure_sender()
        self._sender.send(payload)

    def recv(self, timeout=None):
        """
        Compatibilité sync recv: déconseillée (bloquante).
        """
        self.sock.settimeout(timeout)
        try:
            data = self.sock.recv(self.server.recv_buffer)
            return Requests.decode(data, self.server.langage)
        except Exception:
            return None

    def ban(self, duration, reason=""):
        ip = self.addr[0]
        expire = time.time() + duration
        self.server.banned[ip] = expire
        if self.server._on_ban:
            self.server._on_ban(self, duration, reason)
        self.close()

    def close(self):
        if not self.running:
            return
        self.running = False
        if self.server.core:
            self.server.core.close_socket(self.sock)
        if self in self.server.clients:
            try:
                self.server.clients.remove(self)
            except ValueError:
                pass


# noinspection PyProtectedMember
class Server:
    """
    Server optimisé mémoire pour Veltix.
    - Garde des mappings fileno -> client pour réduire overhead
    - Handshake non bloquant (start_init) : pas de ThreadPoolExecutor
    - Callbacks maintenus pour compatibilité
    """

    __slots__ = (
        "host",
        "port",
        "recv_buffer",
        "size_history",
        "langage",
        "storage",
        "running",
        # clients maps: fileno->client (TempClient or ServerClient)
        "temp_clients",
        "clients",
        "banned",
        # mapping fileno -> client obj for quick lookup
        "_sock_to_client",
        # core
        "core",
        # callbacks
        "_on_connect",
        "_on_disconnect",
        "_on_message",
        "_on_auth",
        "_on_ban",
        "_on_unban",
        "_on_invalid_request",
        "_on_client_update",
    )

    def __init__(
            self,
            storage: VeltixStorage,
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
        self.langage: Langage = storage.get_langage()
        self.storage = storage
        self.running = False

        # maps fileno -> client (lightweight)
        self.temp_clients: Dict[int, TempClient] = {}
        self.clients: Dict[int, ServerClient] = {}
        # banned ips -> expire
        self.banned: Dict[str, float] = {}

        # core réseau optimisé
        self.core = VxCore(recv_bufsize=recv_buffer)
        self.core.max_conn_per_ip = max_conn_per_ip

        # callbacks privés
        self._on_connect: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None
        self._on_message: Optional[Callable] = None
        self._on_auth: Optional[Callable] = None
        self._on_ban: Optional[Callable] = None
        self._on_unban: Optional[Callable] = None
        self._on_invalid_request: Optional[Callable] = None
        self._on_client_update: Optional[Callable] = None

        # Setup callbacks du core
        self.core.on_connect = self._core_on_connect
        self.core.on_data = self._core_on_data
        self.core.on_close = self._core_on_close

    # === Décorateurs pour binding simple ===
    def on_connect(self, func: Callable):
        self._on_connect = func
        return func

    def on_disconnect(self, func: Callable):
        self._on_disconnect = func
        return func

    def on_message(self, func: Callable):
        self._on_message = func
        return func

    def on_auth(self, func: Callable):
        self._on_auth = func
        return func

    def on_ban(self, func: Callable):
        self._on_ban = func
        return func

    def on_unban(self, func: Callable):
        self._on_unban = func
        return func

    def on_invalid_request(self, func: Callable):
        self._on_invalid_request = func
        return func

    def on_client_update(self, func: Callable):
        self._on_client_update = func
        return func

    # === Helpers légers ===
    @staticmethod
    def _fileno_from_sock(sock):
        try:
            return sock.fileno()
        except Exception:
            return None

    def _register_temp(self, sock, addr):
        """Créer TempClient minimal et l'enregistrer par fileno"""
        temp = TempClient(sock, addr, self)
        fileno = self._fileno_from_sock(sock)
        if fileno is None:
            # fallback close
            try:
                sock.close()
            except Exception:
                pass
            return None
        self.temp_clients[fileno] = temp
        return temp

    def _unregister_client(self, fileno):
        """Retire proprement un client (temp ou auth)"""
        if fileno in self.temp_clients:
            del self.temp_clients[fileno]
            return
        if fileno in self.clients:
            del self.clients[fileno]

    # === Callbacks internes du core ===
    def _core_on_connect(self, sock, addr):
        ip = addr[0]
        self.cleanup_ban()
        if ip in self.banned and self.banned[ip] > time.time():
            self.core.close_socket(sock)
            return

        temp = self._register_temp(sock, addr)
        if temp is None:
            return

        # lance le handshake non bloquant : start_init -> réponse dans temp._handle_data
        try:
            temp.start_init()
        except Exception:
            # si start_init plante, on ferme tout de suite
            temp.close()
            return

        # NOTE: on_connect ne sera appelé que quand le temp deviendra initialisé (temp._handle_data)
        # si tu veux une notification immédiate, gère via on_pending_connect séparé (optionnel)

    def _core_on_data(self, sock, data: memoryview):
        fileno = self._fileno_from_sock(sock)
        if fileno is None:
            return
        # lookup minimal - évite exceptions
        client = None
        if fileno in self.temp_clients:
            client = self.temp_clients[fileno]
        elif fileno in self.clients:
            client = self.clients[fileno]
        if client:
            # déléguer au handler léger (doit être non-bloquant)
            try:
                client._handle_data(data)
            except Exception:
                # si erreur fatale, fermer socket via core (libère recv_buf)
                self.core.close_socket(sock)

    def _core_on_close(self, sock):
        fileno = self._fileno_from_sock(sock)
        if fileno is None:
            return
        # remove from either dict
        client = self.temp_clients.pop(fileno, None) or self.clients.pop(fileno, None)
        # core already closed the socket at this point
        if client:
            try:
                client.running = False
            except Exception:
                pass
            if self._on_disconnect:
                try:
                    self._on_disconnect(client)
                except Exception:
                    pass

    # === Méthodes publiques (compatibilité) ===
    def start(self):
        self.core.start_server(self.host, self.port)
        self.running = True
        print(f"[+] Serveur démarré sur {self.host}:{self.port}")

    def run_forever(self):
        self.start()
        self.core.run_forever()

    def cleanup_ban(self):
        now = time.time()
        # comprehension compacte pour réduire overhead mémoire temporaire
        keys = [k for k, v in self.banned.items() if v <= now]
        for k in keys:
            del self.banned[k]

    def _upgrade_client(self, temp_client: TempClient, new_client: ServerClient):
        # remplace l'entrée temp par l'entrée auth (fileno->client)
        fileno = self._fileno_from_sock(temp_client.sock)
        if fileno is None:
            temp_client.close()
            return
        # supprime temp
        if fileno in self.temp_clients:
            del self.temp_clients[fileno]
        # ajoute client auth
        self.clients[fileno] = new_client
        # met à jour mapping interne si nécessaire (ServerClient.sock reste le même)
        if self._on_auth:
            try:
                self._on_auth(new_client)
            except Exception:
                pass

    def get_all_connection(self):
        # retourne une vue légère (itérable) - évite copie
        return self.clients.values()

    def count_connection(self):
        return len(self.clients)

    def send_all(self, payload: Requests):
        # itère sur view, évite création de liste complète
        for client in list(self.clients.values()):
            try:
                client.send(payload)
            except Exception:
                # si echec d'envoi -> fermer via core (qui nettoiera)
                try:
                    self.core.close_socket(client.sock)
                except Exception:
                    pass

    def get_stats(self):
        base = self.core.get_stats()
        return {
            **base,
            "temp_clients": len(self.temp_clients),
            "auth_clients": len(self.clients),
            "banned_ips": len(self.banned),
        }

    def close(self):
        self.running = False
        self.core.stop()
        print("[x] Serveur arrêté")
