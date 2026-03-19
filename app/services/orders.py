"""Order and payment domain services."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from random import randint

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import MenuItem, Order, OrderItem, OrderStatus, Outlet, Payment, PaymentStatus, User
from app.schemas.order import OrderCreate
from app.schemas.payment import PaymentCreate

TWOPLACES = Decimal("0.01")


def _normalize_amount(amount: Decimal) -> Decimal:
    """Round monetary values to two decimal places."""

    return amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _order_query() -> Select[tuple[Order]]:
    """Build the standard eager-loaded order query."""

    return (
        select(Order)
        .options(
            selectinload(Order.items),
            joinedload(Order.outlet),
            joinedload(Order.student).joinedload(User.role_rel),
            selectinload(Order.payments),
        )
    )


def generate_order_number() -> str:
    """Create a human-readable order reference."""

    return f"ORD-{datetime.now(UTC):%Y%m%d%H%M%S}-{randint(1000, 9999)}"


def create_order(db: Session, student: User, payload: OrderCreate) -> Order:
    """Place a new order, decrement stock, and create a pending payment."""

    menu_ids = [item.menu_item_id for item in payload.items]
    menu_items = db.scalars(
        select(MenuItem).where(MenuItem.id.in_(menu_ids)).options(joinedload(MenuItem.outlet))
    ).all()
    menu_map = {item.id: item for item in menu_items}

    if len(menu_map) != len(set(menu_ids)):
        raise ValueError("One or more menu items were not found.")

    requested_quantities: dict[int, int] = defaultdict(int)
    for line in payload.items:
        requested_quantities[line.menu_item_id] += line.quantity

    outlet_id = payload.outlet_id or menu_items[0].outlet_id
    for item in menu_items:
        if item.outlet_id != outlet_id:
            raise ValueError("All order items must belong to the same outlet.")
        if not item.is_available:
            raise ValueError(f"Menu item '{item.name}' is not available.")
        if item.stock_quantity < requested_quantities[item.id]:
            raise ValueError(f"Insufficient stock for '{item.name}'.")

    outlet = db.scalar(select(Outlet).where(Outlet.id == outlet_id, Outlet.is_active.is_(True)))
    if outlet is None:
        raise ValueError("Selected outlet is not available.")

    order = Order(
        order_number=generate_order_number(),
        student_id=student.id,
        outlet_id=outlet_id,
        status=OrderStatus.pending,
        payment_status=PaymentStatus.pending,
        total_amount=Decimal("0.00"),
    )
    db.add(order)
    db.flush()

    total = Decimal("0.00")
    for line in payload.items:
        menu_item = menu_map[line.menu_item_id]
        line_total = _normalize_amount(Decimal(menu_item.price) * line.quantity)
        total += line_total
        menu_item.stock_quantity -= line.quantity
        db.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=menu_item.id,
                quantity=line.quantity,
                unit_price=_normalize_amount(Decimal(menu_item.price)),
                line_total=line_total,
            )
        )

    order.total_amount = _normalize_amount(total)
    db.add(
        Payment(
            order_id=order.id,
            user_id=student.id,
            provider=payload.payment_method.strip().lower(),
            amount=order.total_amount,
            status=PaymentStatus.pending,
        )
    )
    db.commit()
    return get_order_by_id(db, order.id)


def get_order_by_id(db: Session, order_id: int) -> Order | None:
    """Fetch a single order with its related data."""

    return db.scalar(_order_query().where(Order.id == order_id))


def list_orders_for_user(db: Session, user: User) -> list[Order]:
    """Return the current user's orders, or all orders for admins."""

    statement = _order_query().order_by(Order.created_at.desc())
    if user.role != "admin":
        statement = statement.where(Order.student_id == user.id)
    return list(db.scalars(statement).unique().all())


def update_order_status(db: Session, order: Order, status: str) -> Order:
    """Update the status of an order."""

    normalized = status.strip().lower()
    try:
        order.status = OrderStatus(normalized)
    except ValueError as exc:
        raise ValueError("Invalid order status.") from exc

    db.add(order)
    db.commit()
    return get_order_by_id(db, order.id)


def record_payment(db: Session, actor: User, order: Order, payload: PaymentCreate) -> Payment:
    """Record or update the latest payment row for an order."""

    latest_payment = db.scalar(
        select(Payment)
        .where(Payment.order_id == order.id)
        .order_by(Payment.created_at.desc(), Payment.id.desc())
    )
    if latest_payment is None:
        latest_payment = Payment(
            order_id=order.id,
            user_id=actor.id,
            provider=payload.provider.strip().lower(),
            amount=order.total_amount,
            status=PaymentStatus.pending,
        )
        db.add(latest_payment)

    latest_payment.provider = payload.provider.strip().lower()
    latest_payment.transaction_reference = payload.transaction_reference
    try:
        latest_payment.status = PaymentStatus(payload.status.strip().lower())
    except ValueError as exc:
        raise ValueError("Invalid payment status.") from exc

    order.payment_status = latest_payment.status
    if latest_payment.status == PaymentStatus.paid and order.status == OrderStatus.pending:
        order.status = OrderStatus.confirmed

    db.add(order)
    db.add(latest_payment)
    db.commit()
    db.refresh(latest_payment)
    return latest_payment


def list_payments_for_user(db: Session, user: User) -> list[Payment]:
    """Return payments owned by the user, or all payments for admins."""

    statement = select(Payment).order_by(Payment.created_at.desc())
    if user.role != "admin":
        statement = statement.where(Payment.user_id == user.id)
    return list(db.scalars(statement).all())

