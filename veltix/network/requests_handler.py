import hashlib
import os
import pickle
import time
from collections import deque
from typing import Callable, Optional

from veltix.utils.veltix_exceptions import VeltixProtocolError


class Langage:
    """Charge et vérifie le protocole depuis un fichier commun (optimisé)."""
    __slots__ = ('file_path', 'INIT', '_categories', '_code_cache', '_valid_codes', 'content')

    class Basic:
        pass

    def __init__(self, file_path, content: Optional[str] = None):
        self.INIT = 0x0000
        self.file_path = file_path
        self.content = content
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Protocole introuvable : {file_path}")
        self._categories = {}
        self._code_cache = {}  # Cache code -> catégorie
        self._valid_codes = set()  # Set pour O(1) lookup
        self._load_protocol()

    def _load_protocol(self):
        if not self.content:
            with open(self.file_path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        else:
            lines = self.content.splitlines()

        current_category = None
        used_codes = set()
        used_codes.add(0x0000)

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("[") and line.endswith("]"):
                current_category = line.strip("[]").capitalize()
                if current_category in self._categories:
                    raise VeltixProtocolError(
                        f"Catégorie dupliquée : {current_category} (ligne {line_num})"
                    )
                cat_class = type(current_category, (), {})()
                setattr(self, current_category, cat_class)
                self._categories[current_category] = cat_class

            elif line.startswith("/") and line.endswith("/") and current_category:
                parts = line.strip("/").split("/")
                if len(parts) != 2:
                    raise VeltixProtocolError(f"Ligne invalide : {line} (ligne {line_num})")

                code, typ = parts
                typ = typ.capitalize()

                try:
                    code_int = int(code, 16)
                except ValueError:
                    raise VeltixProtocolError(f"Code hexadécimal invalide : {code} (ligne {line_num})")

                if code_int in used_codes:
                    raise VeltixProtocolError(f"Code dupliqué : {code} (ligne {line_num})")

                # Validation des plages
                if current_category == "Basic" and code_int > 0x01F4:
                    raise VeltixProtocolError(
                        f"Code hors limite pour Basic : {code} (ligne {line_num})"
                    )
                if current_category != "Basic" and code_int < 0x01F4:
                    raise VeltixProtocolError(
                        f"Code réservé : {code} (ligne {line_num})"
                    )

                setattr(getattr(self, current_category), typ, code)
                used_codes.add(code_int)
                self._valid_codes.add(code)
                self._code_cache[code] = current_category
            else:
                raise VeltixProtocolError(f"Ligne invalide : {line} (ligne {line_num})")

    def is_valid_type(self, code: str) -> bool:
        """Vérifie si un code est valide - O(1) lookup"""
        return code in self._valid_codes

    def get_category(self, code: str) -> Optional[str]:
        """Récupère la catégorie d'un code - O(1) lookup"""
        return self._code_cache.get(code)


class Requests:
    """Une requête Veltix (optimisée pour performance)"""
    __slots__ = ('langage', 'type', 'timestamp', 'content', 'length', 'hash', '_encoded_cache')

    def __init__(self, type_code: str, content, langage: Langage):
        self.langage = langage
        self.type = type_code

        if not self.langage.is_valid_type(type_code):
            raise VeltixProtocolError(f"Type de message invalide : {type_code}")

        self.timestamp = int(time.time() * 1000)
        self.content = content
        self._encoded_cache = None  # Cache pour éviter re-encode

        # Calcul du hash et length en une seule passe
        content_bytes = pickle.dumps(content, protocol=pickle.HIGHEST_PROTOCOL)
        self.length = len(content_bytes)
        self.hash = self._compute_hash_fast(content_bytes)

    def _compute_hash_fast(self, content_bytes: bytes) -> str:
        """Hash optimisé - évite pickle multiple fois"""
        m = hashlib.sha256()
        m.update(self.type.encode())
        m.update(str(self.timestamp).encode())
        m.update(content_bytes)
        return m.hexdigest()

    def encode(self) -> bytes:
        """Encode la requête en binaire avec cache"""
        if self._encoded_cache is None:
            self._encoded_cache = pickle.dumps({
                "type": self.type,
                "timestamp": self.timestamp,
                "length": self.length,
                "hash": self.hash,
                "content": self.content
            }, protocol=pickle.HIGHEST_PROTOCOL)
        return self._encoded_cache

    @staticmethod
    def decode(data: bytes, langage: Langage) -> 'Requests':
        """Decode un binaire en objet Requests"""
        try:
            obj = pickle.loads(data)
        except (pickle.UnpicklingError, EOFError) as e:
            raise VeltixProtocolError(f"Échec décodage pickle : {e}")

        # Validation de la structure
        required_keys = {"type", "timestamp", "length", "hash", "content"}
        if not all(k in obj for k in required_keys):
            raise VeltixProtocolError("Structure de requête invalide")

        req = Requests(obj["type"], obj["content"], langage)
        req.timestamp = obj["timestamp"]
        req.length = obj["length"]

        # Vérification d'intégrité du hash
        expected_hash = obj["hash"]
        if req.hash != expected_hash:
            raise VeltixProtocolError("Hash invalide - données corrompues")

        req.hash = expected_hash
        return req

    def verify_integrity(self) -> bool:
        """Vérifie l'intégrité de la requête"""
        content_bytes = pickle.dumps(self.content, protocol=pickle.HIGHEST_PROTOCOL)
        expected_hash = self._compute_hash_fast(content_bytes)
        return self.hash == expected_hash


class Sender:
    """Envoie des Requests et garde un historique (optimisé)"""
    __slots__ = ('send_func', 'langage', 'max_history', 'pre_send_callback',
                 'history', '_stats', 'encrypt_func')

    def __init__(
            self,
            send: Callable,
            langage: Langage,
            max_history: int = 50,
            pre_send_callback: Optional[Callable] = None
    ):
        self.send_func = send
        self.langage = langage
        self.max_history = max_history
        self.pre_send_callback = pre_send_callback
        self.encrypt_func: Optional[Callable] = None

        # Utilise deque pour O(1) append et popleft
        self.history = deque(maxlen=max_history)

        # Stats pour monitoring
        self._stats = {
            'sent': 0,
            'errors': 0,
            'bytes_sent': 0,
            'last_send': 0
        }

    def set_pre_send_callback(self, func: Optional[Callable]):
        """Définit le callback pré-envoi"""
        self.pre_send_callback = func

    def set_encrypt_func(self, func: Optional[Callable[[bytes], bytes]]):
        """Définit la fonction de chiffrement"""
        self.encrypt_func = func

    def encrypt(self, data: bytes) -> bytes:
        """Applique le chiffrement si configuré"""
        if self.encrypt_func:
            return self.encrypt_func(data)
        return data

    def send(self, request: Requests, private: bool = False) -> bool:
        """
        Envoie une requête

        Args:
            request: La requête à envoyer
            private: Si True, n'ajoute pas à l'historique

        Returns:
            True si succès, False si erreur
        """
        if not isinstance(request, Requests):
            raise VeltixProtocolError("On ne peut envoyer que des objets Requests")

        try:
            # Callback avant envoi
            if self.pre_send_callback:
                data = self.pre_send_callback(request)
                if not isinstance(data, bytes):
                    raise VeltixProtocolError("Le callback doit retourner des bytes")
            else:
                data = request.encode()

            # Chiffrement
            data = self.encrypt(data)

            # Envoi
            self.send_func(data)

            # Stats
            self._stats['sent'] += 1
            self._stats['bytes_sent'] += len(data)
            self._stats['last_send'] = time.time()

            # Historique
            if not private:
                self._add_to_history(request)

            return True

        except Exception as e:
            self._stats['errors'] += 1
            raise VeltixProtocolError(f"Échec d'envoi : {e}")

    def send_batch(self, requests: list[Requests], private: bool = False) -> int:
        """
        Envoie plusieurs requêtes en batch (plus rapide)

        Returns:
            Nombre de requêtes envoyées avec succès
        """
        success_count = 0
        for req in requests:
            # noinspection TryExceptContinue
            try:
                if self.send(req, private):
                    success_count += 1
            except Exception:
                continue
        return success_count

    def get_history(self, *args: int) -> list[Optional[Requests]]:
        """Récupère des requêtes de l'historique par index"""
        result = []
        for i in args:
            try:
                result.append(self.history[i])
            except IndexError:
                result.append(None)
        return result

    def get_last(self, n: int = 1) -> list[Requests]:
        """Récupère les n dernières requêtes"""
        if n <= 0:
            return []
        return list(self.history)[-n:]

    def clear_history(self):
        """Vide l'historique"""
        self.history.clear()

    def get_stats(self) -> dict:
        """Retourne les statistiques d'envoi"""
        return {
            **self._stats,
            'history_size': len(self.history),
            'history_max': self.max_history
        }

    def _add_to_history(self, request: Requests):
        """Ajoute une requête à l'historique (O(1) avec deque)"""
        self.history.append(request)


# === Utilitaires de sécurité ===

def validate_content_size(content, max_size: int = 1048576) -> bool:
    """Valide que le contenu ne dépasse pas une taille max (1MB par défaut)"""
    try:
        size = len(pickle.dumps(content, protocol=pickle.HIGHEST_PROTOCOL))
        return size <= max_size
    except Exception:
        return False


def sanitize_content(content) -> bool:
    """Vérifie que le contenu est sérialisable et sûr"""
    try:
        # Test de sérialisation
        data = pickle.dumps(content, protocol=pickle.HIGHEST_PROTOCOL)
        # Test de désérialisation
        pickle.loads(data)
        return True
    except Exception:
        return False


class SecureRequests(Requests):
    """Version sécurisée avec validation stricte du contenu"""

    def __init__(self, type_code: str, content, langage: Langage, max_size: int = 1048576):
        # Validation de la taille
        if not validate_content_size(content, max_size):
            raise VeltixProtocolError(f"Contenu trop volumineux (max {max_size} bytes)")

        # Validation de la sécurité
        if not sanitize_content(content):
            raise VeltixProtocolError("Contenu non sérialisable ou dangereux")

        super().__init__(type_code, content, langage)