from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app import db, limiter
from app.models import (
    Favorite,
    MenuItem,
    Order,
    OrderItem,
    Role,
    ROLE_STUDENT,
    User,
)
from app.services.order_service import OrderService
from app.services.audit_service import log_audit
from app.utils.api_error import APIError
from app.utils.jwt_helper import create_user_tokens, revoke_current_token

compat_bp = Blueprint("compat", __name__, url_prefix="/api")


def _username_to_email(username: str, email: str | None = None) -> str:
    if email:
        return email.strip().lower()
    value = username.strip().lower()
    if "@" in value:
        return value
    return f"{value}@canteen.local"


def _legacy_role(user: User | None) -> str:
    if not user or not user.role or not user.role.name:
        return "student"
    return user.role.name.lower()


def _legacy_user(user: User) -> dict:
    username = user.email.split("@")[0] if user.email else user.name.split(" ")[0].lower()
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "id": user.id,
        "username": username,
        "role": _legacy_role(user),
        "name": user.name,
        "fullName": user.name,
        "email": user.email,
        "phoneNumber": user.phone,
        "collegeId": user.roll_number,
        "department": user.department,
        "profileImage": None,
        "dietaryPreference": "both",
        "createdAt": user.created_at.isoformat() if user.created_at else now_iso,
        "updatedAt": user.updated_at.isoformat() if user.updated_at else now_iso,
    }


def _category_for_item(name: str) -> str:
    value = name.lower()
    if "fried rice" in value or "rice" in value:
        return "Fried Rice"
    if "noodle" in value:
        return "Noodles"
    if "puff" in value:
        return "Puff"
    if "soda" in value or "cola" in value or "drink" in value:
        return "Cool Drinks"
    return "Menu"


def _legacy_product(item: MenuItem) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description or "",
        "price": str(item.price),
        "category": _category_for_item(item.name),
        "imageUrl": f"https://placehold.co/600x400?text={item.name.replace(' ', '+')}",
        "available": bool(item.is_available),
    }


def _legacy_order_status(status: str) -> str:
    normalized = (status or "").upper()
    if normalized in {"PENDING", "PENDING_PAYMENT"}:
        return "pending"
    if normalized == "PREPARING":
        return "preparing"
    if normalized == "READY":
        return "ready"
    if normalized == "COMPLETED":
        return "completed"
    return "cancelled"


def _legacy_order(order: Order) -> dict:
    items = []
    for item in order.order_items:
        menu_item = item.menu_item
        items.append(
            {
                "id": item.id,
                "orderId": order.id,
                "productId": item.menu_item_id,
                "quantity": item.quantity,
                "price": str(item.unit_price),
                "product": _legacy_product(menu_item) if menu_item else None,
            }
        )
    return {
        "id": order.id,
        "userId": order.user_id,
        "status": _legacy_order_status(order.status),
        "total": str(order.total_amount),
        "createdAt": order.created_at.isoformat() if order.created_at else None,
        "items": items,
    }


def _get_or_create_student_role() -> Role:
    role = Role.query.filter_by(name=ROLE_STUDENT).first()
    if role:
        return role
    role = Role(name=ROLE_STUDENT, description="System role: STUDENT")
    db.session.add(role)
    db.session.commit()
    return role


@compat_bp.post("/register")
@limiter.limit("10 per minute")
def legacy_register():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    name = str(payload.get("name") or payload.get("fullName") or "").strip()
    if not username or not password or not name:
        raise APIError("Invalid registration payload.", 400, "validation_error")

    email = _username_to_email(username, payload.get("email"))
    if User.query.filter_by(email=email).first():
        raise APIError("Email already registered.", 409, "conflict")

    role = _get_or_create_student_role()
    user = User(
        name=name,
        email=email,
        phone=payload.get("phoneNumber"),
        role_id=role.id,
        roll_number=payload.get("collegeId"),
        department=payload.get("department"),
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    tokens = create_user_tokens(user)
    log_audit(user.id, "user_register", "user", user.id)
    response = _legacy_user(user)
    response["accessToken"] = tokens.get("access_token")
    response["refreshToken"] = tokens.get("refresh_token")
    return jsonify(response), 201


@compat_bp.post("/login")
@limiter.limit("20 per minute")
def legacy_login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    if not username or not password:
        raise APIError("Invalid login payload.", 400, "validation_error")

    email = _username_to_email(username, payload.get("email"))
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User.query.filter_by(roll_number=username).first()
    if not user or not user.check_password(password):
        raise APIError("Invalid credentials.", 401, "authentication_failed")
    if not user.is_active:
        raise APIError("Account is disabled.", 403, "forbidden")

    tokens = create_user_tokens(user)
    log_audit(user.id, "user_login", "user", user.id)
    response = _legacy_user(user)
    response["accessToken"] = tokens.get("access_token")
    response["refreshToken"] = tokens.get("refresh_token")
    return jsonify(response), 200


@compat_bp.post("/logout")
def legacy_logout():
    if current_user:
        revoke_current_token(current_user)
        log_audit(current_user.id, "user_logout", "user", current_user.id)
    return jsonify({"success": True, "message": "Logged out."}), 200


@compat_bp.get("/user")
@jwt_required()
def legacy_me():
    if current_user is None:
        raise APIError("User not found.", 404, "not_found")
    return jsonify(_legacy_user(current_user)), 200


@compat_bp.get("/products")
def legacy_products():
    items = MenuItem.query.filter_by(is_available=True).order_by(MenuItem.name.asc()).all()
    return jsonify([_legacy_product(item) for item in items]), 200


@compat_bp.get("/products/<int:product_id>")
def legacy_product(product_id: int):
    item = MenuItem.query.get(product_id)
    if not item:
        raise APIError("Product not found.", 404, "not_found")
    return jsonify(_legacy_product(item)), 200


@compat_bp.get("/orders")
@jwt_required()
def legacy_orders():
    orders = (
        Order.query.options(joinedload(Order.order_items).joinedload(OrderItem.menu_item))
        .filter_by(user_id=current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )
    return jsonify([_legacy_order(order) for order in orders]), 200


@compat_bp.post("/orders")
@jwt_required()
@limiter.limit("10 per minute")
def legacy_create_order():
    payload = request.get_json(silent=True) or {}
    items = payload.get("items") or []
    if not isinstance(items, list) or not items:
        raise APIError("Invalid order payload.", 400, "validation_error")

    product_ids = [int(item.get("productId")) for item in items if item.get("productId")]
    if not product_ids:
        raise APIError("No products provided.", 400, "validation_error")

    menu_items = MenuItem.query.filter(MenuItem.id.in_(product_ids)).all()
    if len(menu_items) != len(product_ids):
        raise APIError("One or more products not found.", 404, "not_found")

    outlet_id = menu_items[0].outlet_id
    if any(item.outlet_id != outlet_id for item in menu_items):
        raise APIError("All items must be from the same outlet.", 400, "validation_error")

    mapped_items = []
    for item in items:
        mapped_items.append(
            {
                "menu_item_id": int(item.get("productId")),
                "quantity": int(item.get("quantity", 1)),
            }
        )

    order_payload = {"outlet_id": outlet_id, "items": mapped_items}
    order = OrderService.create_order(current_user.id, order_payload)
    log_audit(current_user.id, "order_created", "order", order.id)
    return jsonify(_legacy_order(order)), 201


@compat_bp.get("/student/profile")
@jwt_required()
def legacy_student_profile():
    if current_user is None:
        raise APIError("User not found.", 404, "not_found")
    return (
        jsonify({"success": True, "message": "Profile fetched.", "data": _legacy_user(current_user)}),
        200,
    )


@compat_bp.put("/student/profile")
@jwt_required()
@limiter.limit("10 per minute")
def legacy_student_profile_update():
    if current_user is None:
        raise APIError("User not found.", 404, "not_found")

    payload = request.get_json(silent=True) or {}
    update_map = {
        "fullName": "name",
        "phoneNumber": "phone",
        "collegeId": "roll_number",
        "department": "department",
    }
    for incoming, field in update_map.items():
        if incoming in payload and payload[incoming]:
            setattr(current_user, field, payload[incoming])

    if payload.get("email"):
        current_user.email = payload["email"].strip().lower()

    db.session.commit()
    log_audit(current_user.id, "profile_update", "user", current_user.id)
    return (
        jsonify({"success": True, "message": "Profile updated.", "data": _legacy_user(current_user)}),
        200,
    )


@compat_bp.get("/student/orders")
@jwt_required()
def legacy_student_orders():
    page = max(int(request.args.get("page", 1)), 1)
    limit = min(max(int(request.args.get("limit", 10)), 1), 25)
    query = Order.query.options(joinedload(Order.order_items).joinedload(OrderItem.menu_item)).filter_by(
        user_id=current_user.id
    )
    q = (request.args.get("q") or "").strip().lower()
    if q:
        if q.isdigit():
            query = query.filter(Order.id == int(q))
        else:
            query = query.filter(func.lower(Order.status).contains(q))

    total_items = query.count()
    total_pages = max((total_items + limit - 1) // limit, 1)
    orders = (
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    all_orders = (
        Order.query.options(joinedload(Order.order_items).joinedload(OrderItem.menu_item))
        .filter_by(user_id=current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )
    total_spent = db.session.query(func.coalesce(func.sum(Order.total_amount), Decimal("0"))).filter_by(
        user_id=current_user.id
    ).scalar()

    active_order = next(
        (
            order
            for order in all_orders
            if _legacy_order_status(order.status) in {"pending", "preparing", "ready"}
        ),
        None,
    )
    last_order = all_orders[0] if all_orders else None

    payload = {
        "items": [_legacy_order(order) for order in orders],
        "pagination": {
            "page": page,
            "limit": limit,
            "totalItems": total_items,
            "totalPages": total_pages,
        },
        "metrics": {
            "totalOrders": len(all_orders),
            "totalSpent": float(total_spent or 0),
            "activeOrder": _legacy_order(active_order) if active_order else None,
            "lastOrder": _legacy_order(last_order) if last_order else None,
        },
    }
    return jsonify({"success": True, "message": "Orders fetched.", "data": payload}), 200


@compat_bp.get("/student/orders/<int:order_id>")
@jwt_required()
def legacy_student_order_detail(order_id: int):
    order = (
        Order.query.options(joinedload(Order.order_items).joinedload(OrderItem.menu_item))
        .filter_by(id=order_id, user_id=current_user.id)
        .first()
    )
    if not order:
        raise APIError("Order not found.", 404, "not_found")
    return jsonify({"success": True, "message": "Order fetched.", "data": _legacy_order(order)}), 200


@compat_bp.get("/student/favorites")
@jwt_required()
def legacy_favorites():
    favorites = (
        Favorite.query.options(joinedload(Favorite.menu_item))
        .filter_by(user_id=current_user.id)
        .order_by(Favorite.created_at.desc())
        .all()
    )
    payload = [
        {
            "id": fav.id,
            "userId": fav.user_id,
            "productId": fav.menu_item_id,
            "createdAt": fav.created_at.isoformat() if fav.created_at else None,
            "product": _legacy_product(fav.menu_item) if fav.menu_item else None,
        }
        for fav in favorites
    ]
    return jsonify({"success": True, "message": "Favorites fetched.", "data": payload}), 200


@compat_bp.post("/student/favorites")
@jwt_required()
def legacy_favorite_add():
    payload = request.get_json(silent=True) or {}
    item_id = payload.get("itemId")
    if not item_id:
        raise APIError("Invalid favorite payload.", 400, "validation_error")

    menu_item = MenuItem.query.get(int(item_id))
    if not menu_item:
        raise APIError("Product not found.", 404, "not_found")

    favorite = Favorite.query.filter_by(user_id=current_user.id, menu_item_id=menu_item.id).first()
    if not favorite:
        favorite = Favorite(user_id=current_user.id, menu_item_id=menu_item.id)
        db.session.add(favorite)
        db.session.commit()

    payload = {
        "id": favorite.id,
        "userId": favorite.user_id,
        "productId": favorite.menu_item_id,
        "createdAt": favorite.created_at.isoformat() if favorite.created_at else None,
        "product": _legacy_product(menu_item),
    }
    return jsonify({"success": True, "message": "Favorite added.", "data": payload}), 201


@compat_bp.delete("/student/favorites/<int:item_id>")
@jwt_required()
def legacy_favorite_remove(item_id: int):
    favorite = Favorite.query.filter_by(user_id=current_user.id, menu_item_id=item_id).first()
    if favorite:
        db.session.delete(favorite)
        db.session.commit()
    return jsonify({"success": True, "message": "Favorite removed.", "data": {"itemId": item_id}}), 200
