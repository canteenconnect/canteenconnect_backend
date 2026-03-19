"""Payment APIs for recording order settlement."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession, get_current_active_user
from app.models import Payment, User
from app.schemas.payment import PaymentCreate, PaymentRead
from app.services.orders import get_order_by_id, list_payments_for_user, record_payment

router = APIRouter()


@router.post(
    "/orders/{order_id}",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record payment for an order",
)
def create_payment(
    db: DbSession,
    order_id: int,
    payload: PaymentCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> PaymentRead:
    """Record payment information for an order."""

    order = get_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if current_user.role != "admin" and order.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Payment access denied.")

    try:
        return record_payment(db, current_user, order, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/me", response_model=list[PaymentRead], summary="List payments for the current user")
def list_my_payments(
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[PaymentRead]:
    """Return payments visible to the current user."""

    return list_payments_for_user(db, current_user)


@router.get("/{payment_id}", response_model=PaymentRead, summary="Get one payment")
def get_payment(
    db: DbSession,
    payment_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> PaymentRead:
    """Return one payment record, enforcing ownership for students."""

    payment = db.scalar(select(Payment).where(Payment.id == payment_id))
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")
    if current_user.role != "admin" and payment.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Payment access denied.")
    return payment

