"""Credential encryption utilities using Fernet symmetric encryption."""

from cryptography.fernet import Fernet
from config import ENCRYPTION_KEY


_fernet = Fernet(ENCRYPTION_KEY.encode()) if ENCRYPTION_KEY else None


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return base64-encoded ciphertext."""
    if not _fernet:
        raise RuntimeError("ENCRYPTION_KEY not configured in .env")
    return _fernet.encrypt(plaintext.encode('utf-8')).decode('utf-8')


def decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext."""
    if not _fernet:
        raise RuntimeError("ENCRYPTION_KEY not configured in .env")
    return _fernet.decrypt(ciphertext.encode('utf-8')).decode('utf-8')


def generate_key() -> str:
    """Generate a new Fernet key (use once, save to .env)."""
    return Fernet.generate_key().decode('utf-8')
