"""Argon2id password hashing and history enforcement — `13` §5.2–§5.3."""

import re

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

PASSWORD_MIN_LENGTH = 8
PASSWORD_HISTORY_LIMIT = 5

# Upper, lower, digit OR special
PASSWORD_COMPLEXITY = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])((?=.*\d)|(?=.*[^A-Za-z0-9])).+$"
)

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    validate_password_policy(password)
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def validate_password_policy(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError("Password must be at least 8 characters")
    if len(password) > 100:
        raise ValueError("Password must be at most 100 characters")
    if not PASSWORD_COMPLEXITY.match(password):
        raise ValueError(
            "Password must include upper and lower case and a digit or special character"
        )


def password_matches_history(password: str, historical_hashes: list[str]) -> bool:
    """Return True if password matches any of the last N stored hashes."""
    for old_hash in historical_hashes:
        try:
            if _hasher.verify(old_hash, password):
                return True
        except VerifyMismatchError:
            continue
    return False
