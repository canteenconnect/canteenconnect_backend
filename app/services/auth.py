"""Authentication and user management services."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models import Role, User
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


def create_user(
    db: Session,
    payload: UserCreate,
    *,
    allow_admin_role: bool = False,
) -> User:
    """Create a new user with a hashed password and attached role."""

    ensure_roles(db)
    requested_role = payload.role.strip().lower() if payload.role else "student"
    if requested_role == "admin" and not allow_admin_role:
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


def build_token_response(user: User) -> TokenResponse:
    """Build a standard bearer token response for the authenticated user."""

    token = create_access_token(str(user.id), user.role)
    return TokenResponse(access_token=token, user=user)


def seed_initial_admin(db: Session, settings: Settings) -> None:
    """Create an initial admin account when bootstrap credentials are provided."""

    if not (
        settings.initial_admin_username
        and settings.initial_admin_email
        and settings.initial_admin_password
    ):
        return

    if get_user_by_identifier(db, settings.initial_admin_username) or db.scalar(
        select(User).where(User.email == settings.initial_admin_email.lower())
    ):
        return

    create_user(
        db,
        UserCreate(
            username=settings.initial_admin_username,
            email=settings.initial_admin_email,
            full_name="Platform Administrator",
            password=settings.initial_admin_password,
            role="admin",
        ),
        allow_admin_role=True,
    )

