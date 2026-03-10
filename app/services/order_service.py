from __future__ import annotations

import secrets
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import joinedload

from app import db
from app.models import (
    MenuItem,
    ORDER_STATUS_PENDING,
    ORDER_STATUS_PENDING_PAYMENT,
    Order,
    OrderItem,
    Outlet,
    PAYMENT_STATUS_CREATED,
    PAYMENT_STATUS_PAID,
)
from app.utils.api_error import APIError


def _parse_decimal(value, field_name: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise APIError(f"Invalid {field_name}.", 400, "validation_error")
    return parsed


def _generate_order_number() -> str:
    for _ in range(10):
        candidate = f"ORD{datetime.utcnow():%y%m%d%H%M%S}{secrets.token_hex(2).upper()}"
        if not Order.query.filter_by(order_number=candidate).first():
            return candidate
    raise APIError("Unable to generate order number. Please retry.", 500, "order_number_failed")


class OrderService:
    @staticmethod
    def create_order(user_id: int, payload: dict):
        try:
            items = payload.get("items")
            if not isinstance(items, list) or not items:
                raise APIError("items must be a non-empty list.", 400, "validation_error")

            outlet_id = payload.get("outlet_id")
            if outlet_id is None:
                raise APIError("outlet_id is required.", 400, "validation_error")
            try:
                outlet_id = int(outlet_id)
            except (TypeError, ValueError):
                raise APIError("outlet_id must be an integer.", 400, "validation_error")

            requested_quantities: dict[int, int] = {}
            for item in items:
                if not isinstance(item, dict):
                    raise APIError("Each item must be an object.", 400, "validation_error")
                menu_item_id = item.get("menu_item_id")
                quantity = item.get("quantity")
                try:
                    menu_item_id = int(menu_item_id)
                    quantity = int(quantity)
                except (TypeError, ValueError):
                    raise APIError(
                        "menu_item_id and quantity must be integers.", 400, "validation_error"
                    )
                if quantity <= 0:
                    raise APIError("quantity must be greater than 0.", 400, "validation_error")
                requested_quantities[menu_item_id] = requested_quantities.get(menu_item_id, 0) + quantity

            outlet = Outlet.query.filter_by(id=outlet_id, is_active=True).first()
            if not outlet:
                raise APIError("Outlet not found or inactive.", 404, "not_found")

            menu_items = (
                MenuItem.query.filter(MenuItem.id.in_(requested_quantities.keys()))
                .with_for_update()
                .all()
            )
            if len(menu_items) != len(requested_quantities):
                raise APIError("One or more menu items were not found.", 404, "not_found")

            for menu_item in menu_items:
                if menu_item.outlet_id != outlet_id:
                    raise APIError("All items must belong to the same outlet.", 400, "validation_error")
                if not menu_item.is_available:
                    raise APIError(
                        f"Menu item '{menu_item.name}' is unavailable.", 400, "unavailable_item"
                    )
                if menu_item.available_quantity < requested_quantities[menu_item.id]:
                    raise APIError(
                        f"Insufficient stock for '{menu_item.name}'.",
                        400,
                        "insufficient_stock",
                    )

            total_amount = Decimal("0.00")
            for menu_item in menu_items:
                total_amount += _parse_decimal(menu_item.price, "price") * requested_quantities[menu_item.id]

            order = Order(
                order_number=_generate_order_number(),
                user_id=user_id,
                outlet_id=outlet_id,
                total_amount=total_amount,
                status=ORDER_STATUS_PENDING_PAYMENT,
                payment_status=PAYMENT_STATUS_CREATED,
            )
            db.session.add(order)
            db.session.flush()

            for menu_item in menu_items:
                quantity = requested_quantities[menu_item.id]
                menu_item.available_quantity -= quantity
                if menu_item.available_quantity <= 0:
                    menu_item.available_quantity = 0
                    menu_item.is_available = False

                line_total = _parse_decimal(menu_item.price, "price") * quantity
                db.session.add(
                    OrderItem(
                        order_id=order.id,
                        menu_item_id=menu_item.id,
                        quantity=quantity,
                        unit_price=menu_item.price,
                        line_total=line_total,
                    )
                )

            db.session.commit()
            return (
                Order.query.options(
                    joinedload(Order.order_items).joinedload(OrderItem.menu_item),
                )
                .filter_by(id=order.id)
                .first()
            )
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def mark_paid(order: Order):
        order.status = ORDER_STATUS_PENDING
        order.payment_status = PAYMENT_STATUS_PAID
        db.session.commit()

    @staticmethod
    def update_status(order: Order, status: str):
        order.status = status
        db.session.commit()
