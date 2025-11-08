from __future__ import annotations
import socket
import threading
import json
import time
from typing import Callable, Optional, Dict, List

from network.requests_handler import Langage, Requests, Sender

class RequestsSize:
    TINY = 512
    SMALL = 2048
    MEDIUM = 4096
    LARGE = 8192
    HUGE = 16384

class BindingHandler:
    """Gestion centralisée des events via décorateurs"""
    def __init__(self):
        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        self.on_message: Optional[Callable] = None
        self.on_auth: Optional[Callable] = None
        self.on_ban: Optional[Callable] = None
        self.on_unban: Optional[Callable] = None
        self.on_invalid_request: Optional[Callable] = None
        self.on_client_update: Optional[Callable] = None

    def _register(self, attr: str, func: Callable):
        if hasattr(self, attr):
            setattr(self, attr, func)
            return func
        raise ValueError(f"Event inconnu : {attr}")

    def connect(self, func: Callable):
        return self._register("on_connect", func)

    def disconnect(self, func: Callable):
        return self._register("on_disconnect", func)

    def message(self, func: Callable):
        return self._register("on_message", func)

    def auth(self, func: Callable):
        return self._register("on_auth", func)

    def ban(self, func: Callable):
        return self._register("on_ban", func)

    def unban(self, func: Callable):
        return self._register("on_unban", func)

    def invalid_request(self, func: Callable):
        return self._register("on_invalid_request", func)

    def client_update(self, func: Callable):
        return self._register("on_client_update", func)


class TempClient:
    def __init__(self, sock: socket.socket, addr: tuple, server: Server):
        self.sock = sock
        self.addr = addr
        self.server = server
        self.running = True
        threading.Thread(target=self._listen, daemon=True).start()

    def _listen(self):
        while self.running:
            try:
                data = self.sock.recv(self.server.recv_buffer)
                if not data:
                    break
                try:
                    payload = json.loads(data.decode())
                except Exception:
                    payload = {"raw": data.decode(errors="ignore")}
                    if self.server.Binding.on_invalid_request:
                        self.server.Binding.on_invalid_request(self, payload)
                if self.server.Binding.on_message:
                    self.server.Binding.on_message(self, payload)
            except (ConnectionResetError, OSError):
                break
        self.close()

    def send(self, payload):
        try:
            self.sock.sendall(json.dumps(payload).encode())
        except:
            self.close()

    def recv(self, timeout=None):
        self.sock.settimeout(timeout)
        try:
            data = self.sock.recv(self.server.recv_buffer)
            return json.loads(data.decode())
        except:
            return None

    def is_auth(self, payload: dict):
        new_client = Client(self.sock, self.addr, self.server, payload)
        self.server._upgrade_client(self, new_client)
        if self.server.Binding.on_auth:
            self.server.Binding.on_auth(new_client)
        return new_client

    def ban(self, duration, reason=""):
        ip = self.addr[0]
        expire = time.time() + duration
        self.server.banned[ip] = expire
        if self.server.Binding.on_ban:
            self.server.Binding.on_ban(self, duration, reason)
        self.close()

    def close(self):
        if not self.running:
            return
        self.running = False
        try:
            self.sock.close()
        except:
            pass
        if self in self.server.temp_clients:
            self.server.temp_clients.remove(self)
        if self.server.Binding.on_disconnect:
            self.server.Binding.on_disconnect(self)
        print(f"[-] TempClient {self.addr} déconnecté")


class Client:
    def __init__(self, sock: socket.socket, addr: tuple, server: Server, payload=None):
        self.sock = sock
        self.addr = addr
        self.server = server
        self.pre_send: Optional[Callable] = None
        self.sender: Sender = Sender(self.sock.sendall, self.server.langage, self.server.size_history, self.pre_send)
        self.running = True
        self._payload = payload or {}
        threading.Thread(target=self._listen, daemon=True).start()
        for k, v in self._payload.items():
            setattr(self, k, v)

    def update_payload(self, payload: dict):
        self._payload.update(payload)
        for k, v in payload.items():
            setattr(self, k, v)
        if self.server.Binding.on_client_update:
            self.server.Binding.on_client_update(self, payload)

    def get(self, key, default=None):
        return self._payload.get(key, default)

    def _listen(self):
        while self.running:
            try:
                data = self.sock.recv(self.server.recv_buffer)
                payload: Optional[Requests] = None
                if not data:
                    break
                try:
                    payload = Requests.decode(data=data, langage=self.server.langage)
                except Exception:
                    if self.server.Binding.on_invalid_request:
                        self.server.Binding.on_invalid_request(self, data)
                    payload = None
                if payload and self.server.Binding.on_message:
                    self.server.Binding.on_message(self, payload)
            except (ConnectionResetError, OSError):
                break
        self.close()

    def set_pre_send_func(self, func: Callable):
        self.sender.set_pre_send_callback(func)

    def send(self, payload: Requests):
        self.sender.send(payload)

    def recv(self, timeout=None):
        self.sock.settimeout(timeout)
        try:
            data = self.sock.recv(self.server.recv_buffer)
            return Requests.decode(data, self.server.langage)
        except:
            return None

    def close(self):
        if not self.running:
            return
        self.running = False
        try:
            self.sock.close()
        except:
            pass
        if self in self.server.clients:
            self.server.clients.remove(self)
        if self.server.Binding.on_disconnect:
            self.server.Binding.on_disconnect(self)
        print(f"[-] Client {self.addr} déconnecté")

    def ban(self, duration, reason=""):
        ip = self.addr[0]
        expire = time.time() + duration
        self.server.banned[ip] = expire
        if self.server.Binding.on_ban:
            self.server.Binding.on_ban(self, duration, reason)
        self.close()


class Server:
    def __init__(self, langage: Langage, host="0.0.0.0", port=5050, size_history=50, recv_buffer=RequestsSize.MEDIUM):
        self.host = host
        self.port = port
        self.recv_buffer = recv_buffer
        self.size_history = size_history
        self.langage = langage
        self.sock: Optional[socket.socket] = None
        self.running = False

        self.temp_clients: List[TempClient] = []
        self.clients: List[Client] = []
        self.banned: Dict[str, float] = {}

        self.Binding = BindingHandler()

    def cleanup_ban(self):
        now = time.time()
        self.banned = {ip: exp for ip, exp in self.banned.items() if exp > now}

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen()
        self.running = True
        print(f"[+] Serveur démarré sur {self.host}:{self.port}")
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while self.running:
            try:
                if self.sock:
                    client_sock, addr = self.sock.accept()
                    ip = addr[0]
                    self.cleanup_ban()
                    if ip in self.banned and self.banned[ip] > time.time():
                        client_sock.close()
                        continue
                    temp_client = TempClient(client_sock, addr, self)
                    self.temp_clients.append(temp_client)
                    if self.Binding.on_connect:
                        self.Binding.on_connect(temp_client)
                else:
                    break
            except OSError:
                break

    def _upgrade_client(self, temp_client: TempClient, new_client: Client):
        if temp_client in self.temp_clients:
            self.temp_clients.remove(temp_client)
        self.clients.append(new_client)
        print(f"[+] Client {new_client.addr} authentifié")

    def get_all_connection(self):
        return self.clients

    def count_connection(self):
        return len(self.clients)

    def send_all(self, payload: Requests):
        for c in self.clients:
            c.send(payload)

    def close(self):
        self.running = False
        for c in self.clients + self.temp_clients:
            c.close()
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        print("[x] Serveur arrêté")
