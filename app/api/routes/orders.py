"""Order placement and status APIs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbSession, get_current_active_user, require_roles
from app.models import User
from app.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate
from app.services.orders import create_order, get_order_by_id, list_orders_for_user, update_order_status

router = APIRouter()


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED, summary="Place an order")
def place_order(
    db: DbSession,
    payload: OrderCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> OrderRead:
    """Place a student order."""

    if current_user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can place orders.")

    try:
        return create_order(db, current_user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/me", response_model=list[OrderRead], summary="List the current user's orders")
def list_my_orders(
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[OrderRead]:
    """Return orders visible to the current user."""

    return list_orders_for_user(db, current_user)


@router.get("/{order_id}", response_model=OrderRead, summary="Get one order")
def get_order(
    db: DbSession,
    order_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> OrderRead:
    """Return a single order, enforcing ownership for students."""

    order = get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if current_user.role != "admin" and order.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Order access denied.")
    return order


@router.patch(
    "/{order_id}/status",
    response_model=OrderRead,
    summary="Update order status",
)
def patch_order_status(
    db: DbSession,
    order_id: int,
    payload: OrderStatusUpdate,
    _: Annotated[
        User,
        Depends(
            require_roles(
                "admin",
                "super_admin",
                "campus_admin",
                "vendor_manager",
                "kitchen_staff",
            )
        ),
    ],
) -> OrderRead:
    """Update order lifecycle status for admin workflows."""

    order = get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    try:
        return update_order_status(db, order, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

