import os
import base64
from typing import Optional
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class X25519SecureChannel:
    def __init__(self, private_key: Optional[x25519.X25519PrivateKey] = None):
        self.private_key = private_key or x25519.X25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        self.shared_key = None  # AES key dérivée

    def generate_shared_key(self, peer_public: x25519.X25519PublicKey):
        # Diffie-Hellman pour obtenir secret partagé
        secret = self.private_key.exchange(peer_public)
        # Dériver une clé AES-256 via HKDF
        self.shared_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'handshake data'
        ).derive(secret)

    def encrypt(self, data: bytes | str) -> str:
        if self.shared_key is None:
            raise ValueError("shared_key not established")
        if isinstance(data, str):
            data = data.encode('utf-8')
        aesgcm = AESGCM(self.shared_key)
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, data, associated_data=None)
        return base64.b64encode(nonce + ct).decode('utf-8')

    def decrypt(self, token: str) -> bytes:
        if self.shared_key is None:
            raise ValueError("shared_key not established")
        data = base64.b64decode(token)
        nonce = data[:12]
        ct = data[12:]
        aesgcm = AESGCM(self.shared_key)
        return aesgcm.decrypt(nonce, ct, associated_data=None)

    def save_private_key(self, path: str):
        with open(path, 'wb') as f:
            f.write(self.private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            ))

    @staticmethod
    def load_private_key(path: str):
        with open(path, 'rb') as f:
            key_bytes = f.read()
        private_key = x25519.X25519PrivateKey.from_private_bytes(key_bytes)
        return X25519SecureChannel(private_key)
