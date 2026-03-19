"""Security helpers for password hashing, JWT handling, and OAuth2 auth.

This module centralizes the security primitives used across the API:

- Argon2 password hashing through ``pwdlib``
- OAuth2 bearer token extraction for protected routes
- JWT creation and parsing for stateless authentication
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/token",
    scheme_name="OAuth2PasswordBearer",
    description=(
        "Submit username or email plus password to `/token` to receive a bearer "
        "token. Reuse the returned access token in the `Authorization: Bearer ...` "
        "header for protected requests."
    ),
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its stored Argon2 hash."""

    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using the recommended Argon2 configuration."""

    return password_hash.hash(password)


def create_access_token(subject: str, role: str, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token for a user.

    Args:
        subject: The user identifier stored as the JWT ``sub`` claim.
        role: The normalized RBAC role stored as the JWT ``role`` claim.
        expires_delta: Optional custom token lifetime. Defaults to the configured
            ``ACCESS_TOKEN_EXPIRE_MINUTES`` value.
    """

    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode a JWT access token and return its payload."""

    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def parse_token_subject(token: str) -> tuple[int, str]:
    """Extract the user ID and role from a bearer token.

    Returns:
        A tuple of ``(user_id, role)`` derived from the decoded JWT payload.
    """

    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
        role = str(payload.get("role", "")).lower()
    except (JWTError, TypeError, ValueError) as exc:
        raise ValueError("Invalid authentication token") from exc

    if not role:
        raise ValueError("Invalid authentication token")
    return user_id, role
