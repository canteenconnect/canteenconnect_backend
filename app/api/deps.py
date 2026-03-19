"""Reusable FastAPI dependencies for database access and RBAC."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import oauth2_scheme, parse_token_subject
from app.models import User

DbSession = Annotated[Session, Depends(get_db)]
TokenDependency = Annotated[str, Depends(oauth2_scheme)]


def get_current_user(db: DbSession, token: TokenDependency) -> User:
    """Return the authenticated user from a bearer token."""

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        user_id, _ = parse_token_subject(token)
    except (ValueError, JWTError) as exc:
        raise credentials_error from exc

    user = (
        db.query(User)
        .options(joinedload(User.role_rel))
        .filter(User.id == user_id)
        .first()
    )
    if user is None:
        raise credentials_error
    return user


def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Ensure the current user is active."""

    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user.")
    return current_user


def require_roles(*allowed_roles: str) -> Callable[[User], User]:
    """Create a dependency that restricts access to one or more roles."""

    normalized_roles = {role.strip().lower() for role in allowed_roles}

    def dependency(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if current_user.role not in normalized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return current_user

    return dependency

