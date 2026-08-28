"""Cryptographic primitives for authentication.

Deliberately dependency-light: Argon2id through ``argon2-cffi`` directly, and
``secrets``/``hashlib`` from the standard library. No Passlib, no JWT, no auth
framework.

Nothing in this module touches the database or FastAPI.
"""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

#: Argon2id parameters, stated explicitly rather than inherited from the
#: library's defaults so that a reviewer can see and challenge them.
_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

#: Length matters more than composition rules, so there are no character-class
#: requirements. The upper bound only stops a multi-megabyte request body from
#: turning into an expensive hash.
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128

#: Session tokens carry ~256 bits of entropy.
_SESSION_TOKEN_BYTES = 32

#: A real Argon2 hash of a value nobody knows, verified when login is attempted
#: for an unknown or inactive account. Without it, a missing account would
#: return measurably faster than a wrong password and leak which emails exist.
_DUMMY_HASH = _HASHER.hash(secrets.token_urlsafe(32))


def normalize_email(email: str) -> str:
    """Return the deterministic form used for uniqueness and lookup."""
    return email.strip().casefold()


def validate_password(password: str) -> None:
    """Raise :class:`ValueError` if the password fails policy.

    Never include the password itself in the message — these propagate into API
    responses and logs.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters.")


def hash_password(password: str) -> str:
    """Return an Argon2id hash. The caller validates policy first."""
    return _HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Whether ``password`` matches ``password_hash``.

    Returns False rather than raising for any verification failure, including a
    malformed stored hash: a corrupt row must not become a 500.
    """
    try:
        return _HASHER.verify(password_hash, password)
    except (Argon2Error, InvalidHashError):
        # Argon2Error covers a wrong password (VerifyMismatchError) and other
        # verification failures; InvalidHashError derives from ValueError, not
        # Argon2Error, and fires when the stored hash itself is malformed.
        return False


def verify_dummy_password(password: str) -> None:
    """Burn the same work as a real verification, then discard the result.

    Called on the unknown-account login path so that response time does not
    distinguish "no such user" from "wrong password".
    """
    verify_password(_DUMMY_HASH, password)


def generate_session_token() -> str:
    """Return a fresh, cryptographically random session token.

    This value is handed to the browser once and never stored anywhere.
    """
    return secrets.token_urlsafe(_SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """Return the SHA-256 hex digest stored in place of the raw token.

    A stolen database dump therefore yields no usable session. SHA-256 is
    correct here and Argon2 is not: the token is already high-entropy random,
    so there is nothing to brute-force, and lookups must be fast and exact.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
