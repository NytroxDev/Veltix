import base64
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


class Ed25519Signer:
    def __init__(self, private_key: Optional[ed25519.Ed25519PrivateKey] = None):
        self.private_key = private_key or ed25519.Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()

    @staticmethod
    def generate():
        return Ed25519Signer()

    def sign(self, data: bytes | str) -> str:
        """Retourne la signature base64"""
        if isinstance(data, str):
            data = data.encode()
        signature = self.private_key.sign(data)
        return base64.b64encode(signature).decode()

    def verify(self, data: bytes | str, signature_b64: str) -> bool:
        if isinstance(data, str):
            data = data.encode()
        signature = base64.b64decode(signature_b64)
        try:
            self.public_key.verify(signature, data)
            return True
        except:
            return False

    def save_private_key(self, path: str, password: Optional[bytes] = None):
        enc_algo = serialization.BestAvailableEncryption(password) if password else serialization.NoEncryption()
        pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=enc_algo
        )
        with open(path, 'wb') as f:
            f.write(pem)

    def save_public_key(self, path: str):
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        with open(path, 'wb') as f:
            f.write(pem)

    @classmethod
    def load_private_key(cls, path: str, password: Optional[bytes] = None):
        with open(path, 'rb') as f:
            pem_data = f.read()
        private_key = serialization.load_pem_private_key(pem_data, password=password)
        return cls(private_key)

    @classmethod
    def load_public_key(cls, path: str):
        with open(path, 'rb') as f:
            pem_data = f.read()
        public_key = serialization.load_pem_public_key(pem_data)
        obj = cls()
        obj.private_key = None
        obj.public_key = public_key
        return obj