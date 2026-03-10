from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user
from sqlalchemy import func

from app import db
from app.middleware.role_required import role_required
from app.models import (
    Order,
    Outlet,
    Payment,
    PAYMENT_STATUS_PAID,
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
    Role,
    User,
)
from app.services.audit_service import log_audit
from app.utils.api_error import APIError

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/users")
@role_required(ROLE_ADMIN, ROLE_SUPER_ADMIN)
def list_users():
    role_name = request.args.get("role")
    query = User.query
    if role_name:
        role = Role.query.filter_by(name=role_name.upper()).first()
        if not role:
            return jsonify({"users": []}), 200
        query = query.filter_by(role_id=role.id)
    users = query.order_by(User.created_at.desc()).all()
    log_audit(current_user.id, "admin_users_list", "user", None)
    return jsonify({"users": [user.to_dict() for user in users]}), 200


@admin_bp.get("/outlets")
@role_required(ROLE_ADMIN, ROLE_SUPER_ADMIN)
def list_outlets():
    outlets = Outlet.query.order_by(Outlet.created_at.desc()).all()
    log_audit(current_user.id, "admin_outlets_list", "outlet", None)
    return jsonify({"outlets": [outlet.to_dict() for outlet in outlets]}), 200


@admin_bp.get("/analytics")
@role_required(ROLE_ADMIN, ROLE_SUPER_ADMIN)
def analytics():
    today = datetime.utcnow().date()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    try:
        if start_date:
            start = datetime.fromisoformat(start_date).date()
        else:
            start = today - timedelta(days=30)

        if end_date:
            end = datetime.fromisoformat(end_date).date()
        else:
            end = today
    except ValueError:
        raise APIError("Dates must be in ISO format (YYYY-MM-DD).", 400, "validation_error")

    revenue_by_day = (
        db.session.query(
            func.date(Payment.created_at).label("date"),
            func.coalesce(func.sum(Payment.amount), 0).label("revenue"),
        )
        .filter(Payment.status == PAYMENT_STATUS_PAID)
        .filter(Payment.created_at >= start, Payment.created_at <= end + timedelta(days=1))
        .group_by(func.date(Payment.created_at))
        .order_by(func.date(Payment.created_at))
        .all()
    )

    orders_by_status = (
        db.session.query(Order.status, func.count(Order.id))
        .group_by(Order.status)
        .all()
    )

    outlet_revenue = (
        db.session.query(
            Outlet.id,
            Outlet.name,
            func.coalesce(func.sum(Payment.amount), 0).label("revenue"),
        )
        .join(Order, Order.outlet_id == Outlet.id)
        .join(Payment, Payment.order_id == Order.id)
        .filter(Payment.status == PAYMENT_STATUS_PAID)
        .group_by(Outlet.id, Outlet.name)
        .order_by(func.coalesce(func.sum(Payment.amount), 0).desc())
        .all()
    )

    peak_hours = (
        db.session.query(
            func.date_part("hour", Order.created_at).label("hour"),
            func.count(Order.id).label("count"),
        )
        .group_by(func.date_part("hour", Order.created_at))
        .order_by(func.count(Order.id).desc())
        .all()
    )

    payload = {
        "revenue_by_day": [
            {"date": str(row.date), "revenue": float(row.revenue)} for row in revenue_by_day
        ],
        "orders_by_status": [
            {"status": row[0], "count": row[1]} for row in orders_by_status
        ],
        "outlet_revenue": [
            {"outlet_id": row.id, "outlet_name": row.name, "revenue": float(row.revenue)}
            for row in outlet_revenue
        ],
        "peak_hours": [{"hour": int(row.hour), "count": row.count} for row in peak_hours],
    }

    log_audit(current_user.id, "admin_analytics_view", "analytics", None)
    return jsonify(payload), 200
