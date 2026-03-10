import secrets
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .exceptions import ServiceError
from .models import MenuItem, Order, OrderItem, Outlet, Payment, Student
from .serializers import order_to_dict, outlet_to_dict


def _parse_decimal(value, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ServiceError(f"Invalid {field_name}", 400, "validation_error") from exc


def _generate_order_number(db: Session) -> str:
    for _ in range(10):
        candidate = f"ORD{datetime.now(timezone.utc):%y%m%d%H%M%S}{secrets.token_hex(2).upper()}"
        exists = db.execute(select(Order).where(Order.order_number == candidate)).scalar_one_or_none()
        if not exists:
            return candidate
    raise ServiceError("Failed to generate order number", 500, "order_number_generation_failed")


def _generate_transaction_id(payment_mode: str) -> str:
    return f"{payment_mode.upper()}-{datetime.now(timezone.utc):%y%m%d%H%M%S}-{secrets.token_hex(3).upper()}"


def place_order(db: Session, user_id: int, payload: dict):
    payment_mode = str(payload.get("payment_mode", "")).strip().lower()
    if payment_mode not in {"wallet", "upi", "cash"}:
        raise ServiceError("payment_mode must be wallet, upi, or cash", 400, "validation_error")

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ServiceError("items must be a non-empty list", 400, "validation_error")

    requested_quantities: dict[int, int] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ServiceError("Each item must be an object", 400, "validation_error")

        menu_item_id = item.get("menu_item_id")
        quantity = item.get("quantity")
        try:
            menu_item_id = int(menu_item_id)
            quantity = int(quantity)
        except (TypeError, ValueError) as exc:
            raise ServiceError("menu_item_id and quantity must be integers", 400, "validation_error") from exc

        if quantity <= 0:
            raise ServiceError("quantity must be greater than 0", 400, "validation_error")

        requested_quantities[menu_item_id] = requested_quantities.get(menu_item_id, 0) + quantity

    outlet_id = payload.get("outlet_id")
    if outlet_id is not None:
        try:
            outlet_id = int(outlet_id)
        except (TypeError, ValueError) as exc:
            raise ServiceError("outlet_id must be an integer", 400, "validation_error") from exc

    student = (
        db.execute(
            select(Student)
            .where(Student.user_id == user_id)
            .with_for_update()
            .options(joinedload(Student.user))
        )
        .scalars()
        .first()
    )
    if not student:
        raise ServiceError("Student profile not found", 404, "not_found")

    menu_item_ids = list(requested_quantities.keys())
    menu_items = (
        db.execute(
            select(MenuItem)
            .where(MenuItem.id.in_(menu_item_ids))
            .with_for_update()
            .options(joinedload(MenuItem.outlet))
        )
        .scalars()
        .all()
    )

    if len(menu_items) != len(menu_item_ids):
        raise ServiceError("One or more menu items were not found", 404, "not_found")

    menu_map = {item.id: item for item in menu_items}
    detected_outlet_id = menu_items[0].outlet_id

    for menu_item_id, quantity in requested_quantities.items():
        menu_item = menu_map[menu_item_id]
        if menu_item.outlet_id != detected_outlet_id:
            raise ServiceError("All items must belong to same outlet", 400, "validation_error")
        if not menu_item.is_available:
            raise ServiceError(f"Menu item {menu_item.item_name} is unavailable", 400, "unavailable_item")
        if menu_item.available_quantity < quantity:
            raise ServiceError(f"Insufficient stock for {menu_item.item_name}", 400, "insufficient_stock")

    if outlet_id is not None and outlet_id != detected_outlet_id:
        raise ServiceError("outlet_id mismatch for selected items", 400, "validation_error")

    outlet_id = detected_outlet_id
    outlet = db.execute(select(Outlet).where(Outlet.id == outlet_id, Outlet.is_active.is_(True))).scalar_one_or_none()
    if not outlet:
        raise ServiceError("Selected outlet is inactive", 400, "inactive_outlet")

    total_amount = Decimal("0")
    for menu_item_id, quantity in requested_quantities.items():
        menu_item = menu_map[menu_item_id]
        total_amount += _parse_decimal(menu_item.price, "menu item price") * quantity

    wallet_balance = _parse_decimal(student.wallet_balance, "wallet balance")
    if payment_mode == "wallet":
        if wallet_balance < total_amount:
            raise ServiceError("Insufficient wallet balance", 400, "insufficient_balance")
        student.wallet_balance = wallet_balance - total_amount

    order = Order(
        order_number=_generate_order_number(db),
        student_id=student.id,
        outlet_id=outlet_id,
        total_amount=total_amount,
        payment_mode=payment_mode,
        status="pending",
    )
    db.add(order)
    db.flush()

    for menu_item_id, quantity in requested_quantities.items():
        menu_item = menu_map[menu_item_id]
        menu_item.available_quantity -= quantity
        if menu_item.available_quantity <= 0:
            menu_item.available_quantity = 0
            menu_item.is_available = False

        db.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=menu_item_id,
                quantity=quantity,
                price=menu_item.price,
            )
        )

    payment = Payment(
        order_id=order.id,
        payment_status="pending" if payment_mode == "cash" else "success",
        transaction_id=payload.get("transaction_id") or _generate_transaction_id(payment_mode),
    )
    db.add(payment)
    db.commit()

    db.refresh(order)
    order = (
        db.execute(
            select(Order)
            .where(Order.id == order.id)
            .options(
                joinedload(Order.order_items).joinedload(OrderItem.menu_item),
                joinedload(Order.payment),
            )
        )
        .scalars()
        .first()
    )

    event_payload = order_to_dict(order, include_items=True, include_payment=True)
    event_payload["student_user_id"] = user_id
    event_payload["outlet"] = outlet_to_dict(outlet)

    return order, event_payload


def update_order_status(db: Session, order_id: int, status: str):
    status = status.strip().lower()
    if status not in {"pending", "preparing", "ready", "completed", "cancelled"}:
        raise ServiceError("Invalid order status", 400, "validation_error")

    order = (
        db.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(joinedload(Order.order_items).joinedload(OrderItem.menu_item), joinedload(Order.payment))
        )
        .scalars()
        .first()
    )
    if not order:
        raise ServiceError("Order not found", 404, "not_found")

    order.status = status
    if status == "completed":
        order.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(order)

    event_payload = order_to_dict(order, include_items=True, include_payment=True)
    return order, event_payload