"""Security helpers for password hashing, JWT handling, and OAuth2 auth."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its stored hash."""

    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using the configured password hashing algorithm."""

    return password_hash.hash(password)


def create_access_token(subject: str, role: str, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token for a user."""

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
    """Extract the user ID and role from a bearer token."""

    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
        role = str(payload.get("role", "")).lower()
    except (JWTError, TypeError, ValueError) as exc:
        raise ValueError("Invalid authentication token") from exc

    if not role:
        raise ValueError("Invalid authentication token")
    return user_id, role
