from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import joinedload

from app import db, socketio
from app.models import ORDER_STATUSES, ROLE_KITCHEN, Order, OrderItem, Student
from app.utils.api_error import APIError
from app.utils.role_required import role_required

kitchen_bp = Blueprint("kitchen", __name__, url_prefix="/api/kitchen")


def _serialize_kitchen_order(order: Order):
    student_name = None
    if order.student and order.student.user:
        student_name = order.student.user.name
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "payment_mode": order.payment_mode,
        "total_amount": float(order.total_amount or 0),
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
        "outlet_id": order.outlet_id,
        "student_id": order.student_id,
        "student_name": student_name,
        "items": [
            {
                "menu_item_id": item.menu_item_id,
                "item_name": item.menu_item.item_name if item.menu_item else None,
                "quantity": item.quantity,
                "price": float(item.price or 0),
            }
            for item in order.order_items
        ],
    }


@kitchen_bp.get("/orders")
@role_required(ROLE_KITCHEN)
def get_orders():
    status_param = request.args.get("status", default="pending", type=str)
    outlet_id = request.args.get("outlet_id", type=int)

    statuses = [value.strip().lower() for value in status_param.split(",") if value.strip()]
    if not statuses:
        statuses = ["pending"]

    invalid = [value for value in statuses if value not in ORDER_STATUSES]
    if invalid:
        raise APIError(
            f"Invalid status values: {', '.join(invalid)}.",
            400,
            "validation_error",
        )

    query = Order.query.options(
        joinedload(Order.order_items).joinedload(OrderItem.menu_item),
        joinedload(Order.student).joinedload(Student.user),
    ).filter(Order.status.in_(statuses))

    if outlet_id is not None:
        query = query.filter(Order.outlet_id == outlet_id)

    orders = query.order_by(Order.created_at.asc()).all()
    return jsonify({"orders": [_serialize_kitchen_order(order) for order in orders]}), 200


@kitchen_bp.put("/orders/<int:order_id>/status")
@role_required(ROLE_KITCHEN)
def update_order_status(order_id: int):
    payload = request.get_json(silent=True) or {}
    next_status = str(payload.get("status", "")).strip().lower()
    if next_status not in ORDER_STATUSES:
        raise APIError(
            f"status must be one of: {', '.join(sorted(ORDER_STATUSES))}.",
            400,
            "validation_error",
        )

    order = (
        Order.query.options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            joinedload(Order.student).joinedload(Student.user),
            joinedload(Order.payment),
        )
        .filter_by(id=order_id)
        .first()
    )
    if not order:
        raise APIError("Order not found.", 404, "not_found")

    order.status = next_status
    if next_status in {"completed", "cancelled"}:
        order.completed_at = datetime.utcnow()
    else:
        order.completed_at = None
    db.session.commit()

    event_payload = order.to_dict(include_items=True, include_payment=True)
    if order.student:
        event_payload["student_user_id"] = order.student.user_id

    socketio.emit("order_status_updated", event_payload)
    socketio.emit("order_status_updated", event_payload, room=f"outlet_{order.outlet_id}")
    if order.student:
        socketio.emit(
            "order_status_updated",
            event_payload,
            room=f"student_{order.student.user_id}",
        )

    return jsonify({"order": event_payload}), 200

