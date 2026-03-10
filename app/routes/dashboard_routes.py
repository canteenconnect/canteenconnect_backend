from datetime import date, datetime, time, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import Integer, cast, func

from app.models import ROLE_ADMIN, ROLE_EXECUTIVE, Order, Outlet, Student, User
from app.utils.api_error import APIError
from app.utils.role_required import role_required

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


def _parse_date(value: str, field_name: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise APIError(
            f"Invalid {field_name}. Use YYYY-MM-DD format.",
            400,
            "validation_error",
        )


def _range_from_query(default_days: int = 30):
    start_date_raw = request.args.get("start_date")
    end_date_raw = request.args.get("end_date")

    if start_date_raw and end_date_raw:
        start_date = _parse_date(start_date_raw, "start_date")
        end_date = _parse_date(end_date_raw, "end_date")
    elif start_date_raw and not end_date_raw:
        start_date = _parse_date(start_date_raw, "start_date")
        end_date = date.today()
    elif not start_date_raw and end_date_raw:
        end_date = _parse_date(end_date_raw, "end_date")
        start_date = end_date - timedelta(days=default_days - 1)
    else:
        end_date = date.today()
        start_date = end_date - timedelta(days=default_days - 1)

    if start_date > end_date:
        raise APIError("start_date cannot be greater than end_date.", 400, "validation_error")

    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date + timedelta(days=1), time.min)
    return start_date, end_date, start_dt, end_dt


@dashboard_bp.get("/overview")
@role_required(ROLE_EXECUTIVE, ROLE_ADMIN)
def overview():
    today = date.today()
    tomorrow = today + timedelta(days=1)

    total_users = User.query.count()
    total_students = Student.query.count()
    total_orders = Order.query.count()
    active_outlets = Outlet.query.filter_by(is_active=True).count()

    today_orders = (
        Order.query.filter(Order.created_at >= today, Order.created_at < tomorrow).count()
    )
    today_revenue = (
        Order.query.with_entities(func.coalesce(func.sum(Order.total_amount), 0))
        .filter(
            Order.created_at >= today,
            Order.created_at < tomorrow,
            Order.status == "completed",
        )
        .scalar()
    )
    total_revenue = (
        Order.query.with_entities(func.coalesce(func.sum(Order.total_amount), 0))
        .filter(Order.status == "completed")
        .scalar()
    )

    return (
        jsonify(
            {
                "total_users": total_users,
                "total_students": total_students,
                "total_orders": total_orders,
                "active_outlets": active_outlets,
                "today_orders": today_orders,
                "today_revenue": float(today_revenue or 0),
                "total_revenue": float(total_revenue or 0),
            }
        ),
        200,
    )


@dashboard_bp.get("/revenue")
@role_required(ROLE_EXECUTIVE, ROLE_ADMIN)
def revenue():
    start_date, end_date, start_dt, end_dt = _range_from_query(default_days=30)

    daily_rows = (
        Order.query.with_entities(
            func.date(Order.created_at).label("day"),
            func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
        )
        .filter(
            Order.status == "completed",
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
        )
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at))
        .all()
    )

    outlet_rows = (
        Outlet.query.with_entities(
            Outlet.id.label("outlet_id"),
            Outlet.name.label("outlet_name"),
            func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
        )
        .join(Order, Order.outlet_id == Outlet.id)
        .filter(
            Order.status == "completed",
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
        )
        .group_by(Outlet.id, Outlet.name)
        .order_by(func.coalesce(func.sum(Order.total_amount), 0).desc())
        .all()
    )

    return (
        jsonify(
            {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "revenue_by_day": [
                    {"day": row.day.isoformat(), "revenue": float(row.revenue or 0)}
                    for row in daily_rows
                ],
                "outlet_revenue_distribution": [
                    {
                        "outlet_id": row.outlet_id,
                        "outlet_name": row.outlet_name,
                        "revenue": float(row.revenue or 0),
                    }
                    for row in outlet_rows
                ],
            }
        ),
        200,
    )


@dashboard_bp.get("/order-distribution")
@role_required(ROLE_EXECUTIVE, ROLE_ADMIN)
def order_distribution():
    start_date, end_date, start_dt, end_dt = _range_from_query(default_days=30)

    distribution_rows = (
        Order.query.with_entities(
            Order.status.label("status"),
            func.count(Order.id).label("count"),
        )
        .filter(Order.created_at >= start_dt, Order.created_at < end_dt)
        .group_by(Order.status)
        .order_by(Order.status.asc())
        .all()
    )

    return (
        jsonify(
            {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "distribution": [
                    {"status": row.status, "count": row.count} for row in distribution_rows
                ],
            }
        ),
        200,
    )


@dashboard_bp.get("/peak-hours")
@role_required(ROLE_EXECUTIVE, ROLE_ADMIN)
def peak_hours():
    start_date, end_date, start_dt, end_dt = _range_from_query(default_days=30)

    hour_rows = (
        Order.query.with_entities(
            cast(func.extract("hour", Order.created_at), Integer).label("hour"),
            func.count(Order.id).label("order_count"),
        )
        .filter(Order.created_at >= start_dt, Order.created_at < end_dt)
        .group_by(cast(func.extract("hour", Order.created_at), Integer))
        .order_by(cast(func.extract("hour", Order.created_at), Integer))
        .all()
    )

    return (
        jsonify(
            {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "peak_hours": [
                    {"hour": int(row.hour), "order_count": row.order_count}
                    for row in hour_rows
                ],
            }
        ),
        200,
    )

