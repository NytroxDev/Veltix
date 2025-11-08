import os
import base64
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

class ChaCha20Manager:
    def __init__(self, key: Optional[bytes] = None):
        # clé 32 octets pour ChaCha20
        self.key = key or os.urandom(32)

    def encrypt(self, data: str | bytes) -> str:
        if isinstance(data, str):
            data = data.encode('utf-8')
        aead = ChaCha20Poly1305(self.key)
        nonce = os.urandom(12)  # 12 octets recommandé
        ct = aead.encrypt(nonce, data, associated_data=None)
        return base64.b64encode(nonce + ct).decode('utf-8')

    def decrypt(self, token: str) -> bytes:
        data = base64.b64decode(token)
        nonce = data[:12]
        ct = data[12:]
        aead = ChaCha20Poly1305(self.key)
        return aead.decrypt(nonce, ct, associated_data=None)

    def save_key(self, path: str):
        with open(path, 'wb') as f:
            f.write(self.key)

    @classmethod
    def load_key(cls, path: str):
        with open(path, 'rb') as f:
            key = f.read()
        return cls(key)