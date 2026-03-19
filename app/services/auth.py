"""Authentication and user management services."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.core.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    TokenClaims,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    parse_token,
    verify_password,
)
from app.models import RefreshToken, RevokedToken, Role, User
from app.schemas.token import TokenResponse
from app.schemas.user import UserCreate

DEFAULT_ROLES: dict[str, str] = {
    "admin": "Platform administrator with full management access.",
    "super_admin": "Executive administrator with cross-campus visibility.",
    "campus_admin": "Campus-level operations administrator.",
    "vendor_manager": "Vendor operations manager with outlet visibility.",
    "kitchen_staff": "Kitchen operations staff for fulfillment workflows.",
    "student": "Student account for browsing menus and placing orders.",
}


class AuthenticationError(ValueError):
    """Raised when authentication or session rotation fails."""


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    """Normalize DB datetimes so naive SQLite values compare safely in UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def ensure_roles(db: Session) -> None:
    """Create the default RBAC roles if they do not already exist."""

    existing_names = {name for name in db.scalars(select(Role.name)).all()}

    for name, description in DEFAULT_ROLES.items():
        if name not in existing_names:
            db.add(Role(name=name, description=description))

    db.commit()


def get_role_by_name(db: Session, role_name: str) -> Role | None:
    """Fetch a role by its normalized name."""

    normalized = role_name.strip().lower()
    return db.scalar(select(Role).where(Role.name == normalized))


def get_user_by_identifier(db: Session, identifier: str) -> User | None:
    """Find a user by username or email."""

    query = (
        select(User)
        .options(selectinload(User.role_rel))
        .where(or_(User.username == identifier, User.email == identifier))
    )
    return db.scalar(query)


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Find a user by primary key with role information preloaded."""

    return db.scalar(
        select(User).options(selectinload(User.role_rel)).where(User.id == user_id)
    )


def create_user(
    db: Session,
    payload: UserCreate,
    *,
    allow_admin_role: bool = False,
) -> User:
    """Create a new user with a hashed password and attached role."""

    ensure_roles(db)
    requested_role = payload.role.strip().lower() if payload.role else "student"
    if requested_role in {"admin", "super_admin", "campus_admin", "vendor_manager", "kitchen_staff"} and not allow_admin_role:
        requested_role = "student"

    if get_user_by_identifier(db, payload.username):
        raise ValueError("Username is already in use.")
    if db.scalar(select(User).where(User.email == payload.email)):
        raise ValueError("Email is already in use.")

    role = get_role_by_name(db, requested_role)
    if role is None:
        raise ValueError(f"Unsupported role '{requested_role}'.")

    user = User(
        username=payload.username.strip(),
        email=str(payload.email).lower(),
        full_name=payload.full_name.strip(),
        hashed_password=get_password_hash(payload.password),
        role_rel=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(user, attribute_names=["role_rel"])
    return user


def authenticate_user(db: Session, identifier: str, password: str) -> User | None:
    """Authenticate a user by username/email and password."""

    user = get_user_by_identifier(db, identifier.strip())
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def _build_refresh_record(
    *,
    user: User,
    token_jti: str,
    family_id: str,
    expires_at: datetime,
    user_agent: str | None,
    ip_address: str | None,
) -> RefreshToken:
    """Create a database row for a freshly issued refresh token."""

    return RefreshToken(
        user_id=user.id,
        token_jti=token_jti,
        family_id=family_id,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )


def _upsert_revoked_token(
    db: Session,
    *,
    user_id: int,
    token_jti: str,
    token_type: str,
    expires_at: datetime,
    reason: str,
) -> None:
    """Insert a token into the revocation list if it is not already present."""

    existing = db.scalar(select(RevokedToken).where(RevokedToken.token_jti == token_jti))
    if existing is not None:
        return

    db.add(
        RevokedToken(
            user_id=user_id,
            token_jti=token_jti,
            token_type=token_type,
            reason=reason,
            expires_at=expires_at,
        )
    )


def revoke_refresh_family(db: Session, family_id: str, *, reason: str) -> None:
    """Revoke every refresh token that belongs to the provided family."""

    now = utc_now()
    records = db.scalars(
        select(RefreshToken).where(RefreshToken.family_id == family_id)
    ).all()
    for record in records:
        if record.revoked_at is None:
            record.revoked_at = now
        _upsert_revoked_token(
            db,
            user_id=record.user_id,
            token_jti=record.token_jti,
            token_type=REFRESH_TOKEN_TYPE,
            expires_at=record.expires_at,
            reason=reason,
        )


def build_token_response(
    db: Session,
    user: User,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> TokenResponse:
    """Build and persist a new access/refresh token pair for a user."""

    access = create_access_token(str(user.id), user.role)
    refresh = create_refresh_token(str(user.id), user.role)
    db.add(
        _build_refresh_record(
            user=user,
            token_jti=refresh.jti,
            family_id=refresh.family_id or refresh.jti,
            expires_at=refresh.expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    )
    db.commit()
    db.refresh(user, attribute_names=["role_rel"])
    return TokenResponse(
        access_token=access.token,
        refresh_token=refresh.token,
        user=user,
    )


def rotate_refresh_token(
    db: Session,
    refresh_token: str,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> TokenResponse:
    """Rotate a valid refresh token and return a fresh token pair."""

    claims = parse_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
    user = get_user_by_id(db, claims.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Refresh token is no longer valid.")

    stored_token = db.scalar(
        select(RefreshToken).where(
            RefreshToken.user_id == claims.user_id,
            RefreshToken.token_jti == claims.jti,
        )
    )
    if stored_token is None:
        raise AuthenticationError("Refresh token is no longer valid.")

    now = utc_now()
    if stored_token.revoked_at is not None or ensure_utc(stored_token.expires_at) <= now:
        raise AuthenticationError("Refresh token is no longer valid.")

    if stored_token.replaced_by_jti:
        revoke_refresh_family(
            db,
            stored_token.family_id,
            reason="refresh_reuse_detected",
        )
        db.commit()
        raise AuthenticationError("Refresh token reuse detected. Please sign in again.")

    access = create_access_token(str(user.id), user.role)
    next_refresh = create_refresh_token(
        str(user.id),
        user.role,
        family_id=stored_token.family_id,
    )

    stored_token.replaced_by_jti = next_refresh.jti
    stored_token.rotated_at = now
    db.add(
        _build_refresh_record(
            user=user,
            token_jti=next_refresh.jti,
            family_id=next_refresh.family_id or stored_token.family_id,
            expires_at=next_refresh.expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    )
    db.commit()
    db.refresh(user, attribute_names=["role_rel"])
    return TokenResponse(
        access_token=access.token,
        refresh_token=next_refresh.token,
        user=user,
    )


def revoke_access_token(db: Session, claims: TokenClaims, *, reason: str) -> None:
    """Blocklist a single access token until it naturally expires."""

    _upsert_revoked_token(
        db,
        user_id=claims.user_id,
        token_jti=claims.jti,
        token_type=ACCESS_TOKEN_TYPE,
        expires_at=claims.expires_at,
        reason=reason,
    )


def logout_user(
    db: Session,
    access_token: str,
    *,
    refresh_token: str | None = None,
) -> None:
    """Revoke the current access token and optionally the matching refresh family."""

    access_claims = parse_token(access_token, expected_type=ACCESS_TOKEN_TYPE)
    revoke_access_token(db, access_claims, reason="logout")

    if refresh_token:
        try:
            refresh_claims = parse_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
        except ValueError:
            refresh_claims = None

        if refresh_claims and refresh_claims.user_id == access_claims.user_id:
            revoke_refresh_family(
                db,
                refresh_claims.family_id or refresh_claims.jti,
                reason="logout",
            )

    db.commit()


def seed_initial_admin(db: Session, settings: Settings) -> None:
    """Create an initial admin account when bootstrap credentials are provided."""

    if not (
        settings.initial_admin_username
        and settings.initial_admin_email
        and settings.initial_admin_password
    ):
        return

    normalized_email = settings.initial_admin_email.lower()
    if get_user_by_identifier(db, settings.initial_admin_username) or db.scalar(
        select(User).where(User.email == normalized_email)
    ):
        return

    create_user(
        db,
        UserCreate(
            username=settings.initial_admin_username,
            email=normalized_email,
            full_name=settings.initial_admin_full_name,
            password=settings.initial_admin_password,
            role=settings.initial_admin_role,
        ),
        allow_admin_role=True,
    )
