from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user
from sqlalchemy.orm import joinedload

from app import db, limiter
from app.middleware.role_required import role_required
from app.models import (
    ORDER_STATUSES,
    ORDER_STATUS_CANCELLED,
    ORDER_STATUS_COMPLETED,
    Order,
    OrderItem,
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
    ROLE_VENDOR,
)
from app.services.audit_service import log_audit
from app.utils.api_error import APIError

vendor_bp = Blueprint("vendor", __name__, url_prefix="/vendor")


@vendor_bp.get("/orders")
@role_required(ROLE_VENDOR, ROLE_ADMIN, ROLE_SUPER_ADMIN)
def list_vendor_orders():
    status = request.args.get("status")
    query = Order.query.options(joinedload(Order.order_items).joinedload(OrderItem.menu_item))

    if current_user.role.name == ROLE_VENDOR:
        if not current_user.outlet_id:
            raise APIError("Vendor outlet not configured.", 400, "configuration_error")
        query = query.filter_by(outlet_id=current_user.outlet_id)

    if status:
        query = query.filter_by(status=status.upper())

    orders = query.order_by(Order.created_at.desc()).all()
    return jsonify({"orders": [order.to_dict(include_items=True) for order in orders]}), 200


@vendor_bp.patch("/orders/<int:order_id>/status")
@role_required(ROLE_VENDOR, ROLE_ADMIN, ROLE_SUPER_ADMIN)
@limiter.limit("30 per minute")
def update_order_status(order_id: int):
    payload = request.get_json(silent=True) or {}
    status = str(payload.get("status", "")).upper()
    if status not in ORDER_STATUSES:
        raise APIError("Invalid status.", 400, "validation_error")
    if status in {ORDER_STATUS_CANCELLED, ORDER_STATUS_COMPLETED} and current_user.role.name == ROLE_VENDOR:
        raise APIError("Vendors cannot set terminal statuses.", 403, "forbidden")

    order = Order.query.filter_by(id=order_id).first()
    if not order:
        raise APIError("Order not found.", 404, "not_found")

    if current_user.role.name == ROLE_VENDOR and order.outlet_id != current_user.outlet_id:
        raise APIError("Order does not belong to your outlet.", 403, "forbidden")

    order.status = status
    db.session.commit()
    log_audit(current_user.id, "order_status_updated", "order", order.id, {"status": status})
    return jsonify({"order": order.to_dict(include_items=True)}), 200
