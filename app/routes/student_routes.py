from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user
from marshmallow import ValidationError
from sqlalchemy.orm import joinedload

from app import limiter
from app.middleware.role_required import role_required
from app.models import MenuItem, Order, OrderItem, ROLE_STUDENT
from app.schemas.order import OrderCreateSchema
from app.services.audit_service import log_audit
from app.services.order_service import OrderService
from app.utils.api_error import APIError

student_bp = Blueprint("student", __name__)


@student_bp.get("/menu")
@role_required(ROLE_STUDENT)
def get_menu():
    outlet_id = request.args.get("outlet_id", type=int)
    query = MenuItem.query.filter_by(is_available=True)
    if outlet_id:
        query = query.filter_by(outlet_id=outlet_id)
    items = query.order_by(MenuItem.name.asc()).all()
    return jsonify({"menu": [item.to_dict() for item in items]}), 200


@student_bp.post("/orders")
@role_required(ROLE_STUDENT)
@limiter.limit("10 per minute")
def create_order():
    payload = request.get_json(silent=True) or {}
    schema = OrderCreateSchema()
    try:
        data = schema.load(payload)
    except ValidationError as err:
        raise APIError("Invalid order payload.", 400, "validation_error", err.messages)

    order = OrderService.create_order(current_user.id, data)
    log_audit(current_user.id, "order_created", "order", order.id)
    return jsonify({"order": order.to_dict(include_items=True)}), 201


@student_bp.get("/orders/my")
@role_required(ROLE_STUDENT)
def my_orders():
    orders = (
        Order.query.options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
        )
        .filter_by(user_id=current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )
    return jsonify({"orders": [order.to_dict(include_items=True) for order in orders]}), 200


@student_bp.get("/orders/<int:order_id>")
@role_required(ROLE_STUDENT)
def get_order(order_id: int):
    order = (
        Order.query.options(
            joinedload(Order.order_items).joinedload(OrderItem.menu_item),
        )
        .filter_by(id=order_id, user_id=current_user.id)
        .first()
    )
    if not order:
        raise APIError("Order not found.", 404, "not_found")
    return jsonify({"order": order.to_dict(include_items=True)}), 200
