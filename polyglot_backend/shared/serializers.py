from typing import Any

from .models import MenuItem, Order, OrderItem, Outlet, Payment, Setting, Student, User


def user_to_dict(user: User) -> dict[str, Any]:
    payload = {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
    if user.student:
        payload["student"] = student_to_dict(user.student)
    return payload


def student_to_dict(student: Student) -> dict[str, Any]:
    return {
        "id": student.id,
        "user_id": student.user_id,
        "roll_number": student.roll_number,
        "department": student.department,
        "wallet_balance": float(student.wallet_balance or 0),
        "created_at": student.created_at.isoformat() if student.created_at else None,
    }


def outlet_to_dict(outlet: Outlet) -> dict[str, Any]:
    return {
        "id": outlet.id,
        "name": outlet.name,
        "location": outlet.location,
        "is_active": outlet.is_active,
        "created_at": outlet.created_at.isoformat() if outlet.created_at else None,
    }


def menu_item_to_dict(item: MenuItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "outlet_id": item.outlet_id,
        "item_name": item.item_name,
        "description": item.description,
        "price": float(item.price or 0),
        "available_quantity": item.available_quantity,
        "is_available": item.is_available,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def order_item_to_dict(order_item: OrderItem) -> dict[str, Any]:
    return {
        "id": order_item.id,
        "order_id": order_item.order_id,
        "menu_item_id": order_item.menu_item_id,
        "quantity": order_item.quantity,
        "price": float(order_item.price or 0),
        "item_name": order_item.menu_item.item_name if order_item.menu_item else None,
    }


def payment_to_dict(payment: Payment) -> dict[str, Any]:
    return {
        "id": payment.id,
        "order_id": payment.order_id,
        "payment_status": payment.payment_status,
        "transaction_id": payment.transaction_id,
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
    }


def order_to_dict(order: Order, include_items: bool = True, include_payment: bool = True) -> dict[str, Any]:
    payload = {
        "id": order.id,
        "order_number": order.order_number,
        "student_id": order.student_id,
        "outlet_id": order.outlet_id,
        "total_amount": float(order.total_amount or 0),
        "payment_mode": order.payment_mode,
        "status": order.status,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
    }
    if include_items:
        payload["items"] = [order_item_to_dict(item) for item in order.order_items]
    if include_payment and order.payment:
        payload["payment"] = payment_to_dict(order.payment)
    return payload


def setting_to_dict(setting: Setting) -> dict[str, Any]:
    return {"id": setting.id, "key": setting.key, "value": setting.value}