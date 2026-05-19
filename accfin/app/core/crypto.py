"""Fernet field encryption for TOTP secrets — `13` §2.3, `06` §3.1."""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().privacy_encryption_key.strip()
    return Fernet(key.encode() if isinstance(key, str) else key)


def reset_fernet_cache() -> None:
    _fernet.cache_clear()


def encrypt_field(value: str) -> str:
    if not value:
        return value
    return _fernet().encrypt(value.encode()).decode()


def decrypt_field(encrypted: str) -> str:
    if not encrypted:
        return encrypted
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt field") from exc
