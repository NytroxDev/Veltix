from veltix.crypto.ChaCha20_handler import ChaCha20Manager
from veltix.crypto.ed25519_handler import Ed25519Signer
from veltix.crypto.x25519_handler import X25519SecureChannel


def generate_private_sign(path):
    signer = Ed25519Signer.generate()
    priv_key = signer.private_key
    pub_key = signer.public_key

    signer.save_private_key(path / "private_key_sign.pem")
    signer.save_public_key(path / "public_key_sign.pem")

    return priv_key, pub_key


def get_signer(path):
    signer = Ed25519Signer.load_private_key(path / "private_key_sign.pem")
    return signer


def verify_sign(signer: Ed25519Signer, data: bytes | str, signature_b64: str):
    return signer.verify(data, signature_b64)


def sign(signer: Ed25519Signer, data: bytes | str):
    return signer.sign(data)


def generate_x25519_key():
    x25519 = X25519SecureChannel()
    priv_key = x25519.private_key
    pub_key = x25519.public_key

    return priv_key, pub_key


def trade_keys_chacha20(priv_key_x25519, peer_key_x25519):
    x25519 = X25519SecureChannel(priv_key_x25519)
    x25519.generate_shared_key(peer_key_x25519)
    keys = ChaCha20Manager(x25519.shared_key)
    return keys


def encrypt_chacha20(keys: ChaCha20Manager, data: bytes | str):
    return keys.encrypt(data)


def decrypt_chacha20(keys: ChaCha20Manager, data: str):
    return keys.decrypt(data)
