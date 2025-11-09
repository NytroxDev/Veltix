import base64
import os
from typing import Union, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class AESManager:
    def __init__(self, key: Optional[bytes] = None):
        """
        key: 16/24/32 bytes (AES-128/192/256)
        Si None, génère une clé AES-256 aléatoire
        """
        if key is None:
            self.key = os.urandom(32)
        else:
            if len(key) not in (16, 24, 32):
                raise ValueError("La clé AES doit faire 16, 24 ou 32 octets")
            self.key = key

    @staticmethod
    def derive_key_from_password(password: str, salt: Optional[bytes] = None, iterations: int = 200_000):
        """
        Retourne (clé, salt) dérivée d'un mot de passe
        """
        if salt is None:
            salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations
        )
        key = kdf.derive(password.encode())
        return key, salt

    def encrypt(self, data: Union[str, bytes]) -> str:
        """
        Retourne une string base64 contenant nonce + ciphertext + tag
        """
        if isinstance(data, str):
            data = data.encode()
        aesgcm = AESGCM(self.key)
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, data, associated_data=None)
        blob = nonce + ct
        return base64.b64encode(blob).decode()

    def decrypt(self, token: str) -> bytes:
        """
        Déchiffre un string base64 (nonce + ciphertext + tag)
        Retourne les bytes. Si l'entrée est un string d'origine, faire .decode('utf-8').
        """
        data = base64.b64decode(token)
        nonce = data[:12]
        ct_and_tag = data[12:]
        aesgcm = AESGCM(self.key)
        return aesgcm.decrypt(nonce, ct_and_tag, associated_data=None)

    def encrypt_file(self, input_path: str, output_path: str):
        with open(input_path, 'rb') as f:
            data = f.read()
        enc = self.encrypt(data)
        with open(output_path, 'w') as f:
            f.write(enc)

    def decrypt_file(self, input_path: str, output_path: str):
        with open(input_path) as f:
            enc = f.read()
        dec = self.decrypt(enc)
        with open(output_path, 'wb') as f:
            f.write(dec)

    def save_key(self, path: str):
        with open(path, 'wb') as f:
            f.write(self.key)

    @classmethod
    def load_key(cls, path: str):
        with open(path, 'rb') as f:
            key = f.read()
        return cls(key)
