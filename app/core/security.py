"""Security helpers for password hashing, JWT handling, and OAuth2 auth.

This module centralizes the security primitives used across the API:

- Argon2 password hashing through ``pwdlib``
- OAuth2 bearer token extraction for protected routes
- JWT creation and parsing for stateless authentication
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hash = PasswordHash.recommended()
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/token",
    scheme_name="OAuth2PasswordBearer",
    description=(
        "Submit username or email plus password to `/token` to receive a bearer "
        "token. Reuse the returned access token in the `Authorization: Bearer ...` "
        "header for protected requests."
    ),
)


@dataclass(frozen=True)
class IssuedToken:
    """Signed JWT plus its server-managed metadata."""

    token: str
    jti: str
    expires_at: datetime
    token_type: str
    family_id: str | None = None


@dataclass(frozen=True)
class TokenClaims:
    """Parsed claims extracted from a JWT."""

    user_id: int
    role: str
    jti: str
    token_type: str
    expires_at: datetime
    family_id: str | None = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its stored Argon2 hash."""

    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using the recommended Argon2 configuration."""

    return password_hash.hash(password)


def _issue_token(
    subject: str,
    role: str,
    *,
    token_type: str,
    expires_delta: timedelta,
    family_id: str | None = None,
) -> IssuedToken:
    """Create a signed JWT with standard session claims."""

    settings = get_settings()
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + expires_delta
    jti = uuid4().hex
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "jti": jti,
        "iat": int(issued_at.timestamp()),
        "exp": expires_at,
    }
    if family_id:
        payload["family"] = family_id

    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return IssuedToken(
        token=token,
        jti=jti,
        expires_at=expires_at,
        token_type=token_type,
        family_id=family_id,
    )


def create_access_token(
    subject: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> IssuedToken:
    """Create a signed JWT access token for a user.

    Args:
        subject: The user identifier stored as the JWT ``sub`` claim.
        role: The normalized RBAC role stored as the JWT ``role`` claim.
        expires_delta: Optional custom token lifetime. Defaults to the configured
            ``ACCESS_TOKEN_EXPIRE_MINUTES`` value.
    """

    settings = get_settings()
    return _issue_token(
        subject,
        role,
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=(
            expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
        ),
    )


def create_refresh_token(
    subject: str,
    role: str,
    *,
    family_id: str | None = None,
    expires_delta: timedelta | None = None,
) -> IssuedToken:
    """Create a signed refresh token that belongs to a rotation family."""

    settings = get_settings()
    resolved_family = family_id or uuid4().hex
    return _issue_token(
        subject,
        role,
        token_type=REFRESH_TOKEN_TYPE,
        expires_delta=(
            expires_delta or timedelta(days=settings.refresh_token_expire_days)
        ),
        family_id=resolved_family,
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode a JWT access token and return its payload."""

    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def parse_token(token: str, *, expected_type: str | None = None) -> TokenClaims:
    """Decode a JWT and return normalized claims."""

    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
        role = str(payload.get("role", "")).lower()
        jti = str(payload.get("jti", ""))
        token_type = str(payload.get("type", "")).lower()
        exp_raw = payload.get("exp")
        if isinstance(exp_raw, datetime):
            expires_at = exp_raw
        elif isinstance(exp_raw, (int, float)):
            expires_at = datetime.fromtimestamp(exp_raw, tz=timezone.utc)
        else:
            raise ValueError("Invalid token expiry")
        family_id = payload.get("family")
        if family_id is not None:
            family_id = str(family_id)
    except (JWTError, TypeError, ValueError) as exc:
        raise ValueError("Invalid authentication token") from exc

    if not role or not jti or not token_type:
        raise ValueError("Invalid authentication token")
    if expected_type and token_type != expected_type:
        raise ValueError("Invalid authentication token")
    return TokenClaims(
        user_id=user_id,
        role=role,
        jti=jti,
        token_type=token_type,
        expires_at=expires_at,
        family_id=family_id,
    )


def parse_token_subject(token: str) -> tuple[int, str]:
    """Extract the user ID and role from a bearer token."""

    claims = parse_token(token, expected_type=ACCESS_TOKEN_TYPE)
    return claims.user_id, claims.role
