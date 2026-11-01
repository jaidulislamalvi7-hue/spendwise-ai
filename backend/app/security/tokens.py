"""JWT creation and verification."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt

from app import config


class TokenError(Exception):
    """Raised when a token is missing, malformed, expired or invalid."""


def create_access_token(subject: UUID | str, expires_minutes: int | None = None) -> str:
    """Create a signed access token for ``subject`` (the user ID)."""
    # Resolved through the module attribute so tests can substitute settings.
    settings = config.get_settings()
    minutes = expires_minutes if expires_minutes is not None else settings.jwt_expire_minutes
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, config.get_jwt_secret(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a token, returning its claims."""
    settings = config.get_settings()
    try:
        claims = jwt.decode(
            token,
            config.get_jwt_secret(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("token is invalid") from exc
    if claims.get("type") != "access":
        raise TokenError("unexpected token type")
    return claims


def token_subject_uuid(token: str) -> UUID:
    """Return the user ID carried by a token."""
    claims = decode_access_token(token)
    try:
        return UUID(str(claims["sub"]))
    except (KeyError, ValueError) as exc:
        raise TokenError("token subject is not a valid user id") from exc
