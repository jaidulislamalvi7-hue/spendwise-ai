"""Password hashing: Argon2 primary, bcrypt fallback.

Argon2id is preferred (memory-hard). bcrypt is used only to verify legacy bcrypt
hashes. Hashes are self-describing, so the verifier always picks the right
algorithm.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


def _argon2() -> PasswordHasher:
    # Library defaults: Argon2id, time_cost=3, memory_cost=64 MiB, parallelism=4.
    return PasswordHasher()


def hash_password(password: str) -> str:
    """Return an Argon2id hash for ``password``."""
    if not password:
        raise ValueError("password must not be empty")
    return _argon2().hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return True when ``password`` matches ``password_hash``.

    Supports Argon2id hashes (current) and bcrypt hashes (fallback).
    """
    if not password or not password_hash:
        return False
    if password_hash.startswith("$argon2"):
        try:
            return _argon2().verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False
    if password_hash.startswith(("$2a$", "$2b$", "$2y$")):
        return _verify_bcrypt(password, password_hash)
    return False


def _verify_bcrypt(password: str, password_hash: str) -> bool:
    """Verify a bcrypt hash, returning False when the backend is unavailable."""
    try:
        import bcrypt
    except ImportError:  # pragma: no cover - bcrypt is part of the api group
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def needs_rehash(password_hash: str) -> bool:
    """Return True when a stored hash should be upgraded to current parameters."""
    if not password_hash.startswith("$argon2"):
        return True
    return _argon2().check_needs_rehash(password_hash)
