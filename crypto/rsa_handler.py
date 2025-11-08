from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
import base64
from typing import Optional, Union

class RSAHandler:
    def __init__(self, private_key=None, public_key=None):
        """
        private_key / public_key: objets cryptography RSA
        """
        self.private_key = private_key
        self.public_key = public_key

    @staticmethod
    def generate_keys(key_size=2048):
        """
        Génère une paire RSA
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size
        )
        public_key = private_key.public_key()
        return RSAHandler(private_key, public_key)

    def encrypt(self, data: Union[str, bytes]) -> str:
        """
        Chiffre une string ou bytes avec la clé publique.
        Retourne base64
        """
        if self.public_key is None:
            raise ValueError("Clé publique non définie")
        if isinstance(data, str):
            data_bytes : bytes = data.encode('utf-8')
        elif isinstance(data, bytes):
            data_bytes : bytes = data
        else:
            raise ValueError("Type d'entrer inconnu : " + str(type(data)))
        ciphertext = self.public_key.encrypt(
            data_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(ciphertext).decode('utf-8')

    def decrypt(self, token: str) -> bytes:
        """
        Déchiffre base64 avec la clé privée
        """
        if self.private_key is None:
            raise ValueError("Clé privée non définie")
        ciphertext = base64.b64decode(token)
        plaintext = self.private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return plaintext

    def save_private_key(self, path: str, password: Optional[bytes] = None):
        """
        Sauvegarde la clé privée en PEM, optionnellement chiffrée
        """
        if self.private_key:
            enc_algo = serialization.BestAvailableEncryption(password) if password else serialization.NoEncryption()
            pem = self.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=enc_algo
            )
            with open(path, 'wb') as f:
                f.write(pem)
        else:
            raise ValueError("Clé privée non définie")

    def save_public_key(self, path: str):
        if self.public_key:
            pem = self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            with open(path, 'wb') as f:
                f.write(pem)
        else:
            raise ValueError("Clé publique non définie")

    @classmethod
    def load_private_key(cls, path: str, password: Optional[bytes] = None):
        with open(path, 'rb') as f:
            pem_data = f.read()
        private_key = serialization.load_pem_private_key(pem_data, password=password)
        return cls(private_key=private_key, public_key=private_key.public_key())

    @classmethod
    def load_public_key(cls, path: str):
        with open(path, 'rb') as f:
            pem_data = f.read()
        public_key = serialization.load_pem_public_key(pem_data)
        return cls(public_key=public_key)
