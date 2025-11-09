import json
import threading
import time
from enum import Enum, auto
from pathlib import Path
from queue import Queue, Empty
from typing import Optional, Any

from veltix.crypto.aes_handler import AESManager
from veltix.network.requests_handler import Langage
from veltix.storage.atomic import AtomicFile
from veltix.utils.veltix_exceptions import VeltixStorageError


class LogCategory(Enum):
    GENERAL = auto()
    NETWORK = auto()
    SECURITY = auto()
    SYSTEM = auto()
    AUTH = auto()
    STORAGE = auto()
    CUSTOM = auto()

    def __str__(self):
        return self.name.lower()


class LogLevel(Enum):
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()

    def __str__(self):
        return self.name

class VeltixStorage:
    """
    Gestionnaire de stockage et de logs Veltix.
    - Chargement Langage avec détection chiffrée
    - Journalisation atomique (synchrone ou asynchrone)
    """

    def __init__(self, path: Path, mdp: Optional[str] = None, version: Optional[int] = None, log_mode: str = "sync"):
        self.path = path
        self.mdp = mdp
        self.version = version
        self.log_mode = log_mode.lower()

        if not path.exists():
            raise VeltixStorageError("Le chemin n'existe pas")
        if not path.is_dir():
            raise VeltixStorageError("Le chemin n'est pas un dossier")

        # === Gestion des logs ===
        self.logs_path = path / "veltix_logs.jsonl"
        self._log_file = AtomicFile(str(self.logs_path))
        self._log_queue = Queue()
        self._log_thread: Optional[threading.Thread] = None
        self._log_stop = threading.Event()

        # Démarrage auto seulement si async
        if self.log_mode == "async":
            self.logs_start()

        # Chargement automatique du langage
        self.langage = self.get_langage()

    # === Gestion du langage ===
    def get_langage(self) -> Optional[Langage]:
        file_path = self.path / "langage.vltx"
        if not file_path.exists():
            return None

        with open(file_path, "rb") as f:
            header = f.read(7)
            if header == b"ENCRYPT":
                if not self.mdp:
                    raise VeltixStorageError("Mot de passe requis pour déchiffrer le langage")

                salt = f.read(16)
                encrypted_data = f.read().decode()

                key, _ = AESManager.derive_key_from_password(self.mdp, salt=salt)
                aes = AESManager(key)
                content = aes.decrypt(encrypted_data).decode()

                return Langage(file_path, content)
            else:
                f.seek(0)
                return Langage(file_path, f.read().decode())

    def save_langage(self, content: str):
        """Sauvegarde du fichier langage, chiffré si mot de passe fourni"""
        file_path = self.path / "langage.vltx"
        if self.mdp:
            key, salt = AESManager.derive_key_from_password(self.mdp)
            aes = AESManager(key)
            encrypted = aes.encrypt(content)

            with open(file_path, "wb") as f:
                f.write(b"ENCRYPT")
                f.write(salt)
                f.write(encrypted.encode())
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

    # === Logs : flexible (sync/async) ===
    def logs_add(
            self,
            message: str,
            category: LogCategory = LogCategory.GENERAL,
            level: LogLevel = LogLevel.INFO,
            data: Optional[Any] = None
    ):
        """
        Ajoute un log.
        Compatible Enum pour category et level.
        """
        log_entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "category": str(category),
            "level": str(level),
            "message": message,
            "data": data,
        }

        if self.log_mode == "async" and self._log_thread is not None:
            self._log_queue.put(log_entry)
        else:
            self._write_logs([log_entry])

    def _write_logs(self, logs: list[dict]):
        """Écrit un lot de logs de manière atomique"""
        if not logs:
            return
        log_lines = "\n".join(json.dumps(l, ensure_ascii=False) for l in logs) + "\n"
        existing = self._log_file.read() or ""
        self._log_file.write(existing + log_lines)

    # === Mode asynchrone ===
    def logs_start(self):
        """Démarre le thread de logs asynchrone"""
        if self._log_thread and self._log_thread.is_alive():
            return  # déjà lancé
        self._log_stop.clear()
        self._log_thread = threading.Thread(target=self._log_worker, daemon=True)
        self._log_thread.start()

    def logs_stop(self):
        """Arrête proprement le thread de logs"""
        if not self._log_thread:
            return
        self._log_stop.set()
        self._log_thread.join(timeout=2)
        self._log_thread = None
        self.logs_flush()

    def _log_worker(self):
        """Thread de fond : flush périodique"""
        buffer = []
        last_flush = time.time()

        while not self._log_stop.is_set():
            try:
                log = self._log_queue.get(timeout=1)
                buffer.append(log)
            except Empty:
                pass

            if buffer and (len(buffer) >= 20 or time.time() - last_flush >= 2):
                self._write_logs(buffer)
                buffer.clear()
                last_flush = time.time()

        # Flush final
        if buffer:
            self._write_logs(buffer)

    def logs_flush(self):
        """Force l'écriture de tous les logs restants"""
        while not self._log_queue.empty():
            time.sleep(0.05)

    # === Lecture des logs ===
    def logs_get(self, last_n: int = 50, category: Optional[str] = None) -> list[dict]:
        """Récupère les derniers logs (filtrage possible)"""
        data = self._log_file.read()
        if not data:
            return []
        logs = [json.loads(line) for line in data.splitlines() if line.strip()]
        if category:
            logs = [l for l in logs if l["category"] == category]
        return logs[-last_n:]

    def close(self):
        """Arrêt propre (si async)"""
        if self.log_mode == "async":
            self.logs_stop()

    @staticmethod
    def create_veltix(path: Path, name: str, content: str = "", encrypt: bool = False, password: Optional[str] = None):
        """
        Crée un fichier .veltix de manière atomique et sécurisée.

        Args:
            path (Path): Dossier de destination.
            name (str): Nom du fichier (sans extension .veltix).
            content (str): Contenu initial du fichier.
            encrypt (bool): Si True, le contenu sera chiffré avec AES (clé dérivée du mot de passe).
            password (str, optional): Mot de passe utilisé pour le chiffrement.
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
            file_path = path / f"{name}.veltix"
            atomic = AtomicFile(str(file_path))

            if encrypt:
                if not password:
                    raise VeltixStorageError("Mot de passe requis pour créer un fichier .veltix chiffré")

                key, salt = AESManager.derive_key_from_password(password)
                aes = AESManager(key)
                encrypted = aes.encrypt(content)

                with atomic.open_for_write(mode="wb") as f:
                    f.write(b"ENCRYPT")
                    f.write(salt)
                    f.write(encrypted.encode())
            else:
                with atomic.open_for_write(mode="w", encoding="utf-8") as f:
                    f.write(content)

            return file_path

        except Exception as e:
            raise VeltixStorageError(f"Échec de la création du fichier .veltix : {e}")
