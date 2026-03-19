"""Admin-only management endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import DbSession, require_roles
from app.models import Outlet, User
from app.schemas.order import OrderRead
from app.schemas.outlet import OutletCreate, OutletRead
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.auth import create_user, get_role_by_name
from app.services.orders import list_orders_for_user

router = APIRouter()

ADMIN_READ_ROLES = ("admin", "super_admin", "campus_admin")
ADMIN_WRITE_ROLES = ("admin", "super_admin", "campus_admin")
ORDER_MANAGEMENT_ROLES = (
    "admin",
    "super_admin",
    "campus_admin",
    "vendor_manager",
    "kitchen_staff",
)
OUTLET_MANAGEMENT_ROLES = ("admin", "super_admin", "campus_admin", "vendor_manager")


@router.get("/users", response_model=list[UserRead], summary="List all users")
def list_users(
    db: DbSession,
    admin_user: Annotated[User, Depends(require_roles(*ADMIN_READ_ROLES))],
) -> list[UserRead]:
    """Return all users for admin management."""

    del admin_user
    return list(db.scalars(select(User).order_by(User.created_at.desc())).all())


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an admin-managed user",
)
def create_managed_user(
    db: DbSession,
    payload: UserCreate,
    _: Annotated[User, Depends(require_roles(*ADMIN_WRITE_ROLES))],
) -> UserRead:
    """Create a user through the admin portal."""

    try:
        return create_user(db, payload, allow_admin_role=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/users/{user_id}", response_model=UserRead, summary="Update an existing user")
def update_managed_user(
    db: DbSession,
    user_id: int,
    payload: UserUpdate,
    _: Annotated[User, Depends(require_roles(*ADMIN_WRITE_ROLES))],
) -> UserRead:
    """Update user metadata and role from the admin portal."""

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    updates = payload.model_dump(exclude_unset=True)
    if "username" in updates and updates["username"] is not None:
        normalized_username = updates["username"].strip()
        existing = db.scalar(select(User).where(User.username == normalized_username, User.id != user_id))
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is already in use.")
        user.username = normalized_username

    if "email" in updates and updates["email"] is not None:
        normalized_email = str(updates["email"]).lower()
        existing = db.scalar(select(User).where(User.email == normalized_email, User.id != user_id))
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already in use.")
        user.email = normalized_email

    if "full_name" in updates and updates["full_name"] is not None:
        user.full_name = updates["full_name"].strip()

    if "role" in updates and updates["role"] is not None:
        role = get_role_by_name(db, updates["role"])
        if role is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported role.")
        user.role_rel = role

    if "is_active" in updates and updates["is_active"] is not None:
        user.is_active = updates["is_active"]

    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(user, attribute_names=["role_rel"])
    return user


@router.patch("/users/{user_id}/toggle-status", response_model=UserRead, summary="Toggle user active status")
def toggle_user_status(
    db: DbSession,
    user_id: int,
    _: Annotated[User, Depends(require_roles(*ADMIN_WRITE_ROLES))],
) -> UserRead:
    """Activate or deactivate a user from the admin portal."""

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.is_active = not user.is_active
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(user, attribute_names=["role_rel"])
    return user


@router.get("/orders", response_model=list[OrderRead], summary="List all orders")
def list_all_orders(
    db: DbSession,
    admin_user: Annotated[User, Depends(require_roles(*ORDER_MANAGEMENT_ROLES))],
) -> list[OrderRead]:
    """Return all orders for admin workflows."""

    return list_orders_for_user(db, admin_user)


@router.get("/outlets", response_model=list[OutletRead], summary="List all outlets")
def list_all_outlets(
    db: DbSession,
    _: Annotated[User, Depends(require_roles(*OUTLET_MANAGEMENT_ROLES))],
) -> list[OutletRead]:
    """Return every outlet regardless of active status."""

    return list(db.scalars(select(Outlet).order_by(Outlet.created_at.desc())).all())


@router.post(
    "/outlets",
    response_model=OutletRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an outlet",
)
def create_outlet(
    db: DbSession,
    payload: OutletCreate,
    _: Annotated[User, Depends(require_roles(*OUTLET_MANAGEMENT_ROLES))],
) -> OutletRead:
    """Create a new canteen outlet."""

    outlet = Outlet(
        name=payload.name.strip(),
        location=payload.location.strip(),
        is_active=payload.is_active,
    )
    db.add(outlet)
    db.commit()
    db.refresh(outlet)
    return outlet


@router.put("/outlets/{outlet_id}", response_model=OutletRead, summary="Update an outlet")
def update_outlet(
    db: DbSession,
    outlet_id: int,
    payload: OutletCreate,
    _: Annotated[User, Depends(require_roles(*OUTLET_MANAGEMENT_ROLES))],
) -> OutletRead:
    """Update outlet basics used by the admin portal."""

    outlet = db.get(Outlet, outlet_id)
    if outlet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outlet not found.")

    outlet.name = payload.name.strip()
    outlet.location = payload.location.strip()
    outlet.is_active = payload.is_active
    db.add(outlet)
    db.commit()
    db.refresh(outlet)
    return outlet


@router.delete("/outlets/{outlet_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an outlet")
def delete_outlet(
    db: DbSession,
    outlet_id: int,
    _: Annotated[User, Depends(require_roles(*OUTLET_MANAGEMENT_ROLES))],
) -> Response:
    """Delete an outlet and its related menu items."""

    outlet = db.get(Outlet, outlet_id)
    if outlet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outlet not found.")

    db.delete(outlet)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)