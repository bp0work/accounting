"""TOTP helpers — `13` §5.5."""

import secrets
import string

import pyotp

from app.core.config import get_settings


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(*, secret: str, username: str, email: str) -> str:
    issuer = get_settings().totp_issuer
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email or username, issuer_name=issuer)


def verify_totp(*, secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def generate_backup_codes(count: int = 8) -> list[str]:
    alphabet = string.digits
    return ["".join(secrets.choice(alphabet) for _ in range(8)) for _ in range(count)]
