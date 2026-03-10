import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from shared.db import SessionLocal, get_db, init_db
from shared.exceptions import ServiceError
from shared.models import (
    ORDER_STATUSES,
    PAYMENT_MODES,
    USER_ROLES,
    MenuItem,
    Order,
    OrderItem,
    Outlet,
    Setting,
    Student,
    User,
)
from shared.notifier import emit_event
from shared.order_service import place_order, update_order_status
from shared.schemas import (
    CreateMenuItemRequest,
    CreateOutletRequest,
    CreateUserRequest,
    LoginRequest,
    PlaceOrderRequest,
    RefreshRequest,
    RegisterRequest,
    SettingsUpdateRequest,
    UpdateMenuItemRequest,
    UpdateOrderStatusRequest,
    UpdateOutletRequest,
    UpdateUserRequest,
    WalletTopupRequest,
)
from shared.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from shared.seed import seed_data
from shared.serializers import (
    menu_item_to_dict,
    order_to_dict,
    outlet_to_dict,
    setting_to_dict,
    student_to_dict,
    user_to_dict,
)

load_dotenv()

app = FastAPI(title="Canteen Polyglot API", version="1.0.0")

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://canteen-admin.vercel.app,https://canteen-admin-kappa.vercel.app,https://canteen-student.vercel.app,https://canteen-student-portal.vercel.app",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer = HTTPBearer(auto_error=False)
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "canteen_session")
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "canteen_refresh")


@app.on_event("startup")
def on_startup():
    init_db()
    with SessionLocal() as db:
        seed_data(db)


def raise_service_error(exc: ServiceError):
    raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "code": exc.code})


def success(data=None, message="ok"):
    return {"success": True, "message": message, "data": data}


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    token: str | None = None
    if credentials:
        token = credentials.credentials
    elif request.cookies.get(SESSION_COOKIE_NAME):
        token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid access token")

    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def role_guard(*roles):
    def checker(user: Annotated[User, Depends(current_user)]):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return checker


def _compat_role(user: User) -> str:
    if user.role == "student":
        return "student"
    if "vendor" in user.email:
        return "vendor"
    return "admin"


def _compat_username(db: Session, user: User) -> str:
    override = _read_setting(db, f"user_username_{user.id}", None)
    if override:
        return str(override)
    if user.email:
        return user.email.split("@", 1)[0]
    return f"user{user.id}"


def _compat_profile_meta(db: Session, user_id: int) -> dict:
    raw = _read_setting(db, f"user_profile_{user_id}", "{}")
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save_compat_profile_meta(db: Session, user_id: int, data: dict):
    _write_setting(db, f"user_profile_{user_id}", json.dumps(data))


def _compat_user_payload(db: Session, user: User, access_token: str | None = None) -> dict:
    profile = _compat_profile_meta(db, user.id)
    now_iso = datetime.utcnow().isoformat()
    payload = {
        "id": user.id,
        "username": _compat_username(db, user),
        "role": _compat_role(user),
        "name": user.name,
        "fullName": profile.get("fullName") or user.name,
        "email": profile.get("email") or user.email,
        "phoneNumber": profile.get("phoneNumber"),
        "collegeId": profile.get("collegeId"),
        "department": profile.get("department"),
        "profileImage": profile.get("profileImage"),
        "dietaryPreference": profile.get("dietaryPreference", "both"),
        "createdAt": now_iso,
        "updatedAt": now_iso,
    }
    if access_token:
        payload["accessToken"] = access_token
    return payload


def _set_auth_cookies(response: Response, user: User):
    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id, user.role)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        access_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 12,
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 24 * 7,
    )
    return access_token


def _clear_auth_cookies(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME)
    response.delete_cookie(REFRESH_COOKIE_NAME)


def _resolve_user_by_username_or_email(db: Session, username: str) -> User | None:
    lookup = username.strip().lower()
    user = db.execute(select(User).where(func.lower(User.email) == lookup)).scalar_one_or_none()
    if user:
        return user

    users = db.execute(select(User)).scalars().all()
    for row in users:
        candidate = _compat_username(db, row).lower()
        if candidate == lookup:
            return row
    return None


def _product_category(name: str) -> str:
    lowered = (name or "").lower()
    if "fried rice" in lowered:
        return "Fried Rice"
    if "noodles" in lowered:
        return "Noodles"
    if "puff" in lowered:
        return "Puff"
    if any(token in lowered for token in ["cola", "soda", "drink", "fizz"]):
        return "Cool Drinks"
    return "Canteen"


def _product_image(name: str) -> str:
    return f"https://placehold.co/600x400?text={name.replace(' ', '+')}"


def _menu_item_to_product(item: MenuItem) -> dict:
    return {
        "id": item.id,
        "name": item.item_name,
        "description": item.description or "",
        "price": str(item.price),
        "category": _product_category(item.item_name),
        "imageUrl": _product_image(item.item_name),
        "available": bool(item.is_available and item.available_quantity > 0),
    }


def _serialize_compat_order(order: Order) -> dict:
    items = []
    for row in order.order_items:
        product = _menu_item_to_product(row.menu_item)
        items.append(
            {
                "id": row.id,
                "orderId": order.id,
                "productId": row.menu_item_id,
                "quantity": row.quantity,
                "price": str(row.price),
                "product": product,
            }
        )

    student_user_id = order.student.user_id if order.student else None
    return {
        "id": order.id,
        "userId": student_user_id,
        "status": order.status,
        "total": str(order.total_amount),
        "createdAt": order.created_at.isoformat() if order.created_at else datetime.utcnow().isoformat(),
        "items": items,
    }


def _favorites_for_user(db: Session, user_id: int) -> list[int]:
    raw = _read_setting(db, f"user_favorites_{user_id}", "[]")
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [int(item) for item in parsed]
    except Exception:
        pass
    return []


def _save_favorites_for_user(db: Session, user_id: int, favorite_ids: list[int]):
    unique_ids = sorted({int(item) for item in favorite_ids})
    _write_setting(db, f"user_favorites_{user_id}", json.dumps(unique_ids))


PORTAL_ROLES = {
    "SUPER_ADMIN": "SUPER_ADMIN",
    "CAMPUS_ADMIN": "CAMPUS_ADMIN",
    "VENDOR_MANAGER": "VENDOR_MANAGER",
    "KITCHEN_STAFF": "KITCHEN_STAFF",
}


def _portal_role_for_user(user: User) -> str:
    if user.email == "super.admin@smartcampus.io":
        return PORTAL_ROLES["SUPER_ADMIN"]
    if user.role == "kitchen":
        return PORTAL_ROLES["KITCHEN_STAFF"]
    if user.role == "executive":
        return PORTAL_ROLES["SUPER_ADMIN"]
    return PORTAL_ROLES["CAMPUS_ADMIN"]


def _model_role_for_portal(portal_role: str) -> str:
    role = (portal_role or "").upper()
    if role == PORTAL_ROLES["KITCHEN_STAFF"]:
        return "kitchen"
    if role == PORTAL_ROLES["SUPER_ADMIN"]:
        return "executive"
    return "admin"


def _status_key(user_id: int) -> str:
    return f"user_status_{user_id}"


def _portal_role_key(user_id: int) -> str:
    return f"user_portal_role_{user_id}"


def _assigned_outlets_key(user_id: int) -> str:
    return f"user_assigned_outlets_{user_id}"


def _read_setting(db: Session, key: str, default=None):
    setting = db.execute(select(Setting).where(Setting.key == key)).scalar_one_or_none()
    return setting.value if setting and setting.value is not None else default


def _write_setting(db: Session, key: str, value: str):
    setting = db.execute(select(Setting).where(Setting.key == key)).scalar_one_or_none()
    if not setting:
        setting = Setting(key=key, value=value)
        db.add(setting)
    else:
        setting.value = value


def _portal_status_for_user(db: Session, user_id: int) -> str:
    value = _read_setting(db, _status_key(user_id), "Active")
    return "Inactive" if str(value).lower() == "inactive" else "Active"


def _portal_role_override(db: Session, user: User) -> str:
    override = _read_setting(db, _portal_role_key(user.id), None)
    if override in PORTAL_ROLES.values():
        return override
    return _portal_role_for_user(user)


def _portal_assigned_outlets(db: Session, user_id: int) -> list[str]:
    raw = _read_setting(db, _assigned_outlets_key(user_id), "[]")
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _to_portal_order_status(status_value: str) -> str:
    mapping = {
        "pending": "Pending",
        "preparing": "Preparing",
        "ready": "Ready",
        "completed": "Collected",
        "cancelled": "Collected",
    }
    return mapping.get((status_value or "").lower(), "Pending")


def _from_portal_order_status(status_value: str) -> str:
    mapping = {
        "pending": "pending",
        "preparing": "preparing",
        "ready": "ready",
        "collected": "completed",
    }
    return mapping.get((status_value or "").lower(), "pending")


def _portal_payment_mode(mode: str) -> str:
    mapping = {"upi": "UPI", "wallet": "Wallet", "cash": "Cash"}
    return mapping.get((mode or "").lower(), "Cash")


def _serialize_order_for_portal(order: Order) -> dict:
    student_name = order.student.user.name if order.student and order.student.user else "Student"
    outlet_name = order.outlet.name if order.outlet else "Outlet"
    items = []
    subtotal = 0.0
    for row in order.order_items:
        unit_price = float(row.price or 0)
        line_total = unit_price * int(row.quantity)
        subtotal += line_total
        items.append(
            {
                "name": row.menu_item.item_name if row.menu_item else "Item",
                "qty": int(row.quantity),
                "unitPrice": unit_price,
                "lineTotal": line_total,
            }
        )

    tx_ref = order.payment.transaction_id if order.payment else "N/A"
    created_at = order.created_at.isoformat() if order.created_at else datetime.utcnow().isoformat()
    updated_at = order.completed_at.isoformat() if order.completed_at else created_at

    return {
        "id": str(order.id),
        "tenantId": "default",
        "outletId": str(order.outlet_id),
        "outletName": outlet_name,
        "vendorName": outlet_name,
        "tokenNo": int(str(order.id)[-3:]) if order.id else 100,
        "studentName": student_name,
        "items": items,
        "subtotal": subtotal,
        "taxAmount": 0,
        "serviceCharge": 0,
        "amount": float(order.total_amount or 0),
        "status": _to_portal_order_status(order.status),
        "paymentMode": _portal_payment_mode(order.payment_mode),
        "priority": "Normal",
        "createdAt": created_at,
        "updatedAt": updated_at,
        "upiRef": tx_ref if _portal_payment_mode(order.payment_mode) == "UPI" else "N/A",
    }


@app.get("/health")
def health():
    return success({"status": "healthy", "service": "fastapi"}, "healthcheck")


# Legacy compatibility auth/routes used by student portal
@app.post("/api/login")
def compat_login(payload: dict, response: Response, db: Annotated[Session, Depends(get_db)]):
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password are required")

    user = _resolve_user_by_username_or_email(db, username)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = _set_auth_cookies(response, user)
    return _compat_user_payload(db, user, access_token=access_token)


@app.post("/api/register")
def compat_register(payload: dict, response: Response, db: Annotated[Session, Depends(get_db)]):
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    role_in = str(payload.get("role", "student")).strip().lower()
    name = str(payload.get("name", "")).strip()
    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail="Invalid username")
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Invalid password")
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    email = str(payload.get("email", "")).strip().lower() or f"{username}@canteen.local"
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already exists")

    if any(_compat_username(db, row).lower() == username.lower() for row in db.execute(select(User)).scalars().all()):
        raise HTTPException(status_code=409, detail="Username already exists")

    mapped_role = "student" if role_in == "student" else "admin"
    user = User(name=name, email=email, role=mapped_role, password_hash=hash_password(password))
    db.add(user)
    db.flush()

    if mapped_role == "student":
        roll_number = str(payload.get("collegeId") or f"STU-{user.id:04d}")
        department = str(payload.get("department") or "General")
        if db.execute(select(Student).where(Student.roll_number == roll_number)).scalar_one_or_none():
            roll_number = f"STU-{user.id:04d}"
        db.add(Student(user_id=user.id, roll_number=roll_number, department=department, wallet_balance=Decimal("500")))

    _write_setting(db, f"user_username_{user.id}", username)
    profile = {
        "fullName": payload.get("fullName") or name,
        "email": payload.get("email"),
        "phoneNumber": payload.get("phoneNumber"),
        "collegeId": payload.get("collegeId"),
        "department": payload.get("department"),
        "profileImage": payload.get("profileImage"),
        "dietaryPreference": payload.get("dietaryPreference", "both"),
    }
    _save_compat_profile_meta(db, user.id, profile)
    db.commit()
    db.refresh(user)

    access_token = _set_auth_cookies(response, user)
    response.status_code = 201
    return _compat_user_payload(db, user, access_token=access_token)


@app.post("/api/logout")
def compat_logout(response: Response):
    _clear_auth_cookies(response)
    return success({}, "Logged out")


@app.get("/api/user")
def compat_user(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]):
    return _compat_user_payload(db, user, access_token=None)


@app.get("/api/auth/token")
def compat_auth_token(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing session")
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    user = db.get(User, int(payload["sub"]))
    if not user or user.role != "student":
        raise HTTPException(status_code=403, detail="Forbidden")
    return success({"accessToken": token}, "Token issued")


@app.post("/api/auth/refresh")
def compat_refresh(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    payload: dict | None = Body(default=None),
):
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME) or (payload or {}).get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    try:
        payload = decode_token(refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    access_token = create_access_token(user.id, user.role)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        access_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 12,
    )
    return success(
        {
            "accessToken": access_token,
            "access_token": access_token,
            "refresh_token": create_refresh_token(user.id, user.role),
            "token_type": "bearer",
        },
        "Token refreshed",
    )


@app.get("/api/products")
def compat_products(db: Annotated[Session, Depends(get_db)]):
    rows = db.execute(select(MenuItem).order_by(MenuItem.item_name.asc())).scalars().all()
    return [_menu_item_to_product(row) for row in rows]


@app.get("/api/products/{product_id}")
def compat_product_by_id(product_id: int, db: Annotated[Session, Depends(get_db)]):
    row = db.get(MenuItem, product_id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return _menu_item_to_product(row)


@app.get("/api/orders")
def compat_orders(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    student = db.execute(select(Student).where(Student.user_id == user.id)).scalar_one_or_none()
    if not student:
        return []
    rows = (
        db.execute(
            select(Order)
            .where(Order.student_id == student.id)
            .order_by(Order.created_at.desc())
            .options(
                joinedload(Order.student).joinedload(Student.user),
                joinedload(Order.order_items).joinedload(OrderItem.menu_item),
                joinedload(Order.payment),
            )
        )
        .scalars()
        .all()
    )
    return [_serialize_compat_order(row) for row in rows]


@app.post("/api/orders")
async def compat_create_order(
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    items = payload.get("items") or []
    mapped = []
    for row in items:
        mapped.append(
            {
                "menu_item_id": int(row.get("productId")),
                "quantity": int(row.get("quantity")),
            }
        )
    if not mapped:
        raise HTTPException(status_code=400, detail="Order items are required")
    try:
        order, event_payload = place_order(db, user.id, {"payment_mode": "cash", "items": mapped})
    except ServiceError as exc:
        raise_service_error(exc)
    await emit_event("order_created", event_payload)
    return {
        "id": order.id,
        "userId": user.id,
        "status": order.status,
        "total": str(order.total_amount),
        "createdAt": order.created_at.isoformat() if order.created_at else datetime.utcnow().isoformat(),
    }


@app.get("/api/student/profile")
def compat_student_profile(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    profile = _compat_profile_meta(db, user.id)
    now_iso = datetime.utcnow().isoformat()
    data = {
        "id": user.id,
        "fullName": profile.get("fullName") or user.name,
        "email": profile.get("email") or user.email,
        "phoneNumber": profile.get("phoneNumber"),
        "collegeId": profile.get("collegeId"),
        "department": profile.get("department"),
        "profileImage": profile.get("profileImage"),
        "dietaryPreference": profile.get("dietaryPreference", "both"),
        "createdAt": now_iso,
        "updatedAt": now_iso,
    }
    return success(data, "Profile fetched")


@app.put("/api/student/profile")
def compat_student_profile_update(
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    profile = _compat_profile_meta(db, user.id)
    for key in ["fullName", "email", "phoneNumber", "collegeId", "department", "profileImage", "dietaryPreference"]:
        if key in payload:
            profile[key] = payload.get(key)
    if profile.get("fullName"):
        user.name = str(profile["fullName"])
    db.add(user)
    _save_compat_profile_meta(db, user.id, profile)
    db.commit()
    return compat_student_profile(db, user)


@app.get("/api/student/orders")
def compat_student_orders(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    page: int = Query(default=1),
    limit: int = Query(default=10),
    q: str | None = Query(default=None),
):
    student = db.execute(select(Student).where(Student.user_id == user.id)).scalar_one_or_none()
    if not student:
        return success(
            {
                "items": [],
                "pagination": {"page": page, "limit": limit, "totalItems": 0, "totalPages": 0},
                "metrics": {"totalOrders": 0, "totalSpent": 0, "activeOrder": None, "lastOrder": None},
            },
            "Orders fetched",
        )

    rows = (
        db.execute(
            select(Order)
            .where(Order.student_id == student.id)
            .order_by(Order.created_at.desc())
            .options(
                joinedload(Order.student).joinedload(Student.user),
                joinedload(Order.order_items).joinedload(OrderItem.menu_item),
                joinedload(Order.payment),
            )
        )
        .scalars()
        .all()
    )
    serialized = [_serialize_compat_order(row) for row in rows]
    if q:
        needle = q.lower().strip()
        serialized = [row for row in serialized if needle in str(row["id"]).lower()]
    total_items = len(serialized)
    total_pages = (total_items + limit - 1) // limit if limit > 0 else 0
    start = (page - 1) * limit
    paged = serialized[start : start + limit]
    total_spent = float(sum(float(order["total"]) for order in serialized))
    active_order = next((order for order in serialized if order["status"] in {"pending", "preparing", "ready"}), None)
    last_order = serialized[0] if serialized else None

    return success(
        {
            "items": paged,
            "pagination": {"page": page, "limit": limit, "totalItems": total_items, "totalPages": total_pages},
            "metrics": {
                "totalOrders": total_items,
                "totalSpent": total_spent,
                "activeOrder": active_order,
                "lastOrder": last_order,
            },
        },
        "Orders fetched",
    )


@app.get("/api/student/orders/{order_id}")
def compat_student_order_detail(
    order_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    student = db.execute(select(Student).where(Student.user_id == user.id)).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Order not found")
    row = (
        db.execute(
            select(Order)
            .where(Order.id == order_id, Order.student_id == student.id)
            .options(
                joinedload(Order.student).joinedload(Student.user),
                joinedload(Order.order_items).joinedload(OrderItem.menu_item),
                joinedload(Order.payment),
            )
        )
        .scalars()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    return success(_serialize_compat_order(row), "Order fetched")


@app.get("/api/student/favorites")
def compat_student_favorites(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    favorite_ids = _favorites_for_user(db, user.id)
    rows = db.execute(select(MenuItem).where(MenuItem.id.in_(favorite_ids))).scalars().all() if favorite_ids else []
    product_map = {row.id: row for row in rows}
    favorites = []
    for idx, product_id in enumerate(favorite_ids, start=1):
        row = product_map.get(product_id)
        if not row:
            continue
        favorites.append(
            {
                "id": idx,
                "userId": user.id,
                "productId": product_id,
                "createdAt": datetime.utcnow().isoformat(),
                "product": _menu_item_to_product(row),
            }
        )
    return success(favorites, "Favorites fetched")


@app.post("/api/student/favorites")
def compat_student_add_favorite(
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    item_id = int(payload.get("itemId"))
    row = db.get(MenuItem, item_id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    favorite_ids = _favorites_for_user(db, user.id)
    if item_id not in favorite_ids:
        favorite_ids.append(item_id)
        _save_favorites_for_user(db, user.id, favorite_ids)
        db.commit()
    return {
        "success": True,
        "message": "Favorite added",
        "data": {
            "id": len(favorite_ids),
            "userId": user.id,
            "productId": item_id,
            "createdAt": datetime.utcnow().isoformat(),
            "product": _menu_item_to_product(row),
        },
    }


@app.delete("/api/student/favorites/{item_id}")
def compat_student_remove_favorite(
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
):
    favorite_ids = [row for row in _favorites_for_user(db, user.id) if row != item_id]
    _save_favorites_for_user(db, user.id, favorite_ids)
    db.commit()
    return success({"itemId": item_id}, "Favorite removed")


# AUTH
@app.post("/api/auth/register")
def register(payload: RegisterRequest, db: Annotated[Session, Depends(get_db)]):
    if payload.role not in USER_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")

    exists = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Email already exists")

    user = User(
        name=payload.name.strip(),
        email=payload.email.lower().strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()

    if payload.role == "student":
        if not payload.roll_number or not payload.department:
            raise HTTPException(status_code=400, detail="roll_number and department are required for student")

        roll_exists = db.execute(select(Student).where(Student.roll_number == payload.roll_number)).scalar_one_or_none()
        if roll_exists:
            raise HTTPException(status_code=409, detail="roll_number already exists")

        db.add(
            Student(
                user_id=user.id,
                roll_number=payload.roll_number,
                department=payload.department,
                wallet_balance=Decimal("0"),
            )
        )

    db.commit()
    db.refresh(user)

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id, user.role)
    return success(
        {
            "user": user_to_dict(user),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
        "User registered",
    )


@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]):
    user = db.execute(select(User).where(User.email == payload.email.lower().strip())).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return success(
        {
            "user": user_to_dict(user),
            "access_token": create_access_token(user.id, user.role),
            "refresh_token": create_refresh_token(user.id, user.role),
            "token_type": "bearer",
        },
        "Login successful",
    )


@app.get("/api/auth/me")
def me(user: Annotated[User, Depends(current_user)]):
    return success(user_to_dict(user), "Current user")


# STUDENT
@app.get("/api/student/outlets")
def student_outlets(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("student"))],
):
    outlets = db.execute(select(Outlet).where(Outlet.is_active.is_(True)).order_by(Outlet.name.asc())).scalars().all()
    return success([outlet_to_dict(o) for o in outlets], "Outlets fetched")


@app.get("/api/student/menu/{outlet_id}")
def student_menu(
    outlet_id: int,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("student"))],
):
    items = (
        db.execute(select(MenuItem).where(MenuItem.outlet_id == outlet_id).order_by(MenuItem.item_name.asc()))
        .scalars()
        .all()
    )
    return success([menu_item_to_dict(i) for i in items], "Menu fetched")


@app.post("/api/student/order")
async def student_order(
    payload: PlaceOrderRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(role_guard("student"))],
):
    try:
        order, event_payload = place_order(db, user.id, payload.model_dump())
    except ServiceError as exc:
        raise_service_error(exc)

    await emit_event("order_created", event_payload)
    return success(order_to_dict(order, include_items=True, include_payment=True), "Order placed")


@app.get("/api/student/my-orders")
def my_orders(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(role_guard("student"))],
):
    student = db.execute(select(Student).where(Student.user_id == user.id)).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")

    orders = (
        db.execute(
            select(Order)
            .where(Order.student_id == student.id)
            .order_by(Order.created_at.desc())
            .options(joinedload(Order.order_items).joinedload(OrderItem.menu_item), joinedload(Order.payment))
        )
        .scalars()
        .all()
    )
    return success([order_to_dict(o, include_items=True, include_payment=True) for o in orders], "Orders fetched")


@app.post("/api/student/wallet/topup")
def wallet_topup(
    payload: WalletTopupRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(role_guard("student"))],
):
    student = db.execute(select(Student).where(Student.user_id == user.id)).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")

    student.wallet_balance = Decimal(student.wallet_balance) + payload.amount
    db.commit()
    db.refresh(student)
    return success(student_to_dict(student), "Wallet topped up")


# ADMIN USERS
@app.get("/api/admin/users")
def admin_users(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("admin"))],
):
    users = db.execute(select(User).order_by(User.created_at.desc())).scalars().all()
    return success([user_to_dict(u) for u in users], "Users fetched")


@app.post("/api/admin/users")
def admin_create_user(
    payload: CreateUserRequest,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("admin"))],
):
    if payload.role not in USER_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")

    if db.execute(select(User).where(User.email == payload.email.lower().strip())).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already exists")

    user = User(
        name=payload.name.strip(),
        email=payload.email.lower().strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()

    if payload.role == "student":
        if not payload.roll_number or not payload.department:
            raise HTTPException(status_code=400, detail="roll_number and department required for student")
        db.add(
            Student(
                user_id=user.id,
                roll_number=payload.roll_number,
                department=payload.department,
                wallet_balance=Decimal("0"),
            )
        )

    db.commit()
    db.refresh(user)
    return success(user_to_dict(user), "User created")


@app.put("/api/admin/users/{user_id}")
def admin_update_user(
    user_id: int,
    payload: UpdateUserRequest,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("admin"))],
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.email is not None:
        user.email = payload.email.lower().strip()
    if payload.role is not None:
        if payload.role not in USER_ROLES:
            raise HTTPException(status_code=400, detail="Invalid role")
        user.role = payload.role
    if payload.password:
        user.password_hash = hash_password(payload.password)

    if user.role == "student":
        student = db.execute(select(Student).where(Student.user_id == user.id)).scalar_one_or_none()
        if not student:
            if not payload.roll_number or not payload.department:
                raise HTTPException(status_code=400, detail="roll_number and department required for student")
            student = Student(
                user_id=user.id,
                roll_number=payload.roll_number,
                department=payload.department,
                wallet_balance=Decimal("0"),
            )
            db.add(student)
        else:
            if payload.roll_number is not None:
                student.roll_number = payload.roll_number
            if payload.department is not None:
                student.department = payload.department

    db.commit()
    db.refresh(user)
    return success(user_to_dict(user), "User updated")


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("admin"))],
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return success({"id": user_id}, "User deleted")


# ADMIN OUTLETS
@app.get("/api/admin/outlets")
def admin_outlets(db: Annotated[Session, Depends(get_db)], _user: Annotated[User, Depends(role_guard("admin"))]):
    outlets = db.execute(select(Outlet).order_by(Outlet.created_at.desc())).scalars().all()
    return success([outlet_to_dict(o) for o in outlets], "Outlets fetched")


@app.post("/api/admin/outlets")
def admin_create_outlet(
    payload: CreateOutletRequest,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("admin"))],
):
    outlet = Outlet(name=payload.name.strip(), location=payload.location.strip(), is_active=payload.is_active)
    db.add(outlet)
    db.commit()
    db.refresh(outlet)
    return success(outlet_to_dict(outlet), "Outlet created")


@app.put("/api/admin/outlets/{outlet_id}")
def admin_update_outlet(
    outlet_id: int,
    payload: UpdateOutletRequest,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("admin"))],
):
    outlet = db.get(Outlet, outlet_id)
    if not outlet:
        raise HTTPException(status_code=404, detail="Outlet not found")

    if payload.name is not None:
        outlet.name = payload.name.strip()
    if payload.location is not None:
        outlet.location = payload.location.strip()
    if payload.is_active is not None:
        outlet.is_active = payload.is_active

    db.commit()
    db.refresh(outlet)
    return success(outlet_to_dict(outlet), "Outlet updated")


# ADMIN MENU
@app.get("/api/admin/menu/{outlet_id}")
def admin_menu(
    outlet_id: int,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("admin"))],
):
    items = db.execute(select(MenuItem).where(MenuItem.outlet_id == outlet_id).order_by(MenuItem.item_name.asc())).scalars().all()
    return success([menu_item_to_dict(i) for i in items], "Menu fetched")


@app.post("/api/admin/menu")
def admin_create_menu_item(
    payload: CreateMenuItemRequest,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("admin"))],
):
    item = MenuItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return success(menu_item_to_dict(item), "Menu item created")


@app.put("/api/admin/menu/{menu_item_id}")
def admin_update_menu_item(
    menu_item_id: int,
    payload: UpdateMenuItemRequest,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("admin"))],
):
    item = db.get(MenuItem, menu_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return success(menu_item_to_dict(item), "Menu item updated")


@app.delete("/api/admin/menu/{menu_item_id}")
def admin_delete_menu_item(
    menu_item_id: int,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("admin"))],
):
    item = db.get(MenuItem, menu_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    db.delete(item)
    db.commit()
    return success({"id": menu_item_id}, "Menu item deleted")


# ADMIN SETTINGS
@app.get("/api/admin/settings")
def admin_settings(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("admin"))],
):
    settings = db.execute(select(Setting).order_by(Setting.key.asc())).scalars().all()
    return success([setting_to_dict(s) for s in settings], "Settings fetched")


@app.put("/api/admin/settings")
def admin_update_settings(
    payload: SettingsUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("admin"))],
):
    for key, value in payload.values.items():
        setting = db.execute(select(Setting).where(Setting.key == key)).scalar_one_or_none()
        if not setting:
            setting = Setting(key=key)
            db.add(setting)
        setting.value = value

    db.commit()
    settings = db.execute(select(Setting).order_by(Setting.key.asc())).scalars().all()
    return success([setting_to_dict(s) for s in settings], "Settings updated")


# DASHBOARD
@app.get("/api/dashboard/overview")
def dashboard_overview(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("executive", "admin"))],
):
    total_orders = db.execute(select(func.count(Order.id))).scalar_one() or 0
    total_revenue = db.execute(select(func.coalesce(func.sum(Order.total_amount), 0))).scalar_one() or 0
    active_outlets = db.execute(select(func.count(Outlet.id)).where(Outlet.is_active.is_(True))).scalar_one() or 0
    pending_orders = db.execute(select(func.count(Order.id)).where(Order.status.in_(["pending", "preparing"]))).scalar_one() or 0

    return success(
        {
            "total_orders": int(total_orders),
            "total_revenue": float(total_revenue),
            "active_outlets": int(active_outlets),
            "pending_orders": int(pending_orders),
        },
        "Overview fetched",
    )


@app.get("/api/dashboard/revenue")
def dashboard_revenue(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("executive", "admin"))],
):
    rows = db.execute(
        select(
            func.date_trunc("day", Order.created_at).label("day"),
            func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
        )
        .group_by(func.date_trunc("day", Order.created_at))
        .order_by(func.date_trunc("day", Order.created_at).asc())
    ).all()

    data = [{"day": row.day.date().isoformat() if row.day else None, "revenue": float(row.revenue or 0)} for row in rows]
    return success(data, "Revenue by day")


@app.get("/api/dashboard/order-distribution")
def dashboard_order_distribution(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("executive", "admin"))],
):
    status_rows = db.execute(select(Order.status, func.count(Order.id)).group_by(Order.status)).all()
    outlet_rows = db.execute(
        select(Outlet.name, func.coalesce(func.sum(Order.total_amount), 0))
        .join(Order, Order.outlet_id == Outlet.id)
        .group_by(Outlet.name)
        .order_by(func.coalesce(func.sum(Order.total_amount), 0).desc())
    ).all()

    return success(
        {
            "by_status": [{"status": row[0], "count": int(row[1])} for row in status_rows],
            "by_outlet_revenue": [{"outlet": row[0], "revenue": float(row[1] or 0)} for row in outlet_rows],
        },
        "Order distribution",
    )


@app.get("/api/dashboard/peak-hours")
def dashboard_peak_hours(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(role_guard("executive", "admin"))],
):
    rows = db.execute(
        select(func.extract("hour", Order.created_at).label("hour"), func.count(Order.id).label("count"))
        .group_by(func.extract("hour", Order.created_at))
        .order_by(func.extract("hour", Order.created_at).asc())
    ).all()
    return success([{"hour": int(row.hour), "count": int(row.count)} for row in rows], "Peak hours")


# KITCHEN
@app.get("/api/kitchen/orders")
def kitchen_orders(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(role_guard("kitchen", "admin"))],
    status_filter: str = Query(default="pending", alias="status"),
):
    statuses = [status_filter] if status_filter in ORDER_STATUSES else ["pending"]
    orders = (
        db.execute(
            select(Order)
            .where(Order.status.in_(statuses))
            .order_by(Order.created_at.asc())
            .options(joinedload(Order.order_items).joinedload(OrderItem.menu_item), joinedload(Order.payment))
        )
        .scalars()
        .all()
    )
    return success([order_to_dict(o, include_items=True, include_payment=True) for o in orders], "Kitchen orders")


@app.put("/api/kitchen/orders/{order_id}/status")
async def kitchen_update_order_status(
    order_id: int,
    payload: UpdateOrderStatusRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(role_guard("kitchen", "admin"))],
):
    try:
        order, event_payload = update_order_status(db, order_id, payload.status)
    except ServiceError as exc:
        raise_service_error(exc)

    await emit_event("order_status_updated", event_payload)
    return success(order_to_dict(order, include_items=True, include_payment=True), "Order status updated")


# Compatibility routes for admin portal frontend
def _default_tenants():
    return [{"id": "default", "name": "Default Campus", "region": "Main"}]


def _admin_portal_user(db: Session, user: User):
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": _portal_role_override(db, user),
        "status": _portal_status_for_user(db, user.id),
        "tenantId": "default",
        "tenantAccess": ["default"],
        "selectedTenantId": "default",
        "assignedOutletIds": _portal_assigned_outlets(db, user.id),
    }


def _admin_app_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = decode_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = db.get(User, int(payload["sub"]))
    if not user or user.role == "student":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


def _commission_rate_for_outlet(db: Session, outlet_id: int) -> float:
    value = _read_setting(db, f"outlet_commission_rate_{outlet_id}", "10")
    try:
        return float(value)
    except Exception:
        return 10.0


def _vendor_name_for_outlet(db: Session, outlet: Outlet) -> str:
    return _read_setting(db, f"outlet_vendor_name_{outlet.id}", outlet.location or "Campus Vendor")


def _outlet_metrics(db: Session):
    outlets = db.execute(select(Outlet).order_by(Outlet.name.asc())).scalars().all()
    orders = db.execute(select(Order).options(joinedload(Order.outlet))).scalars().all()
    by_outlet: dict[int, list[Order]] = {}
    for row in orders:
        by_outlet.setdefault(row.outlet_id, []).append(row)

    result = []
    for outlet in outlets:
        scoped = by_outlet.get(outlet.id, [])
        gross = float(sum(float(order.total_amount or 0) for order in scoped))
        total_orders = len(scoped)
        active_orders = len([order for order in scoped if order.status not in {"completed", "cancelled"}])
        commission_rate = _commission_rate_for_outlet(db, outlet.id)
        commission_amount = round((gross * commission_rate) / 100, 2)
        result.append(
            {
                "id": str(outlet.id),
                "tenantId": "default",
                "name": outlet.name,
                "vendorName": _vendor_name_for_outlet(db, outlet),
                "commissionRate": commission_rate,
                "status": "Active" if outlet.is_active else "Inactive",
                "grossRevenue": gross,
                "totalOrders": total_orders,
                "activeOrders": active_orders,
                "commissionAmount": commission_amount,
                "aov": round(gross / total_orders, 2) if total_orders else 0,
            }
        )
    return result


@app.post("/api/admin-app/login")
def admin_app_login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]):
    user = db.execute(select(User).where(User.email == payload.email.lower().strip())).scalar_one_or_none()
    if not user or user.role not in {"admin", "kitchen", "executive"}:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if _portal_status_for_user(db, user.id) != "Active":
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "token": create_access_token(user.id, user.role),
        "user": _admin_portal_user(db, user),
        "tenants": _default_tenants(),
    }


@app.get("/api/admin-app/tenants")
def admin_app_tenants(_user: Annotated[User, Depends(_admin_app_user)]):
    return _default_tenants()


@app.get("/api/admin-app/orders")
def admin_app_orders(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    rows = (
        db.execute(
            select(Order)
            .order_by(Order.created_at.desc())
            .options(
                joinedload(Order.student).joinedload(Student.user),
                joinedload(Order.outlet),
                joinedload(Order.payment),
                joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            )
        )
        .scalars()
        .all()
    )
    return [_serialize_order_for_portal(order) for order in rows]


@app.get("/api/admin-app/orders/live")
def admin_app_orders_live(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    rows = (
        db.execute(
            select(Order)
            .where(Order.status.in_(["pending", "preparing", "ready"]))
            .order_by(Order.created_at.desc())
            .options(
                joinedload(Order.student).joinedload(Student.user),
                joinedload(Order.outlet),
                joinedload(Order.payment),
                joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            )
        )
        .scalars()
        .all()
    )
    return {
        "orders": [_serialize_order_for_portal(order) for order in rows],
        "generated": {"generated": False, "order": None},
    }


@app.get("/api/admin-app/orders/{order_id}")
def admin_app_get_order(
    order_id: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    try:
        parsed_id = int(order_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Order not found") from exc

    order = (
        db.execute(
            select(Order)
            .where(Order.id == parsed_id)
            .options(
                joinedload(Order.student).joinedload(Student.user),
                joinedload(Order.outlet),
                joinedload(Order.payment),
                joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            )
        )
        .scalars()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _serialize_order_for_portal(order)


@app.patch("/api/admin-app/orders/{order_id}/status")
async def admin_app_update_order_status(
    order_id: str,
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    try:
        parsed_id = int(order_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Order not found") from exc

    next_status = _from_portal_order_status(str(payload.get("status", "")))
    try:
        order, event_payload = update_order_status(db, parsed_id, next_status)
    except ServiceError as exc:
        raise_service_error(exc)

    await emit_event("order_status_updated", event_payload)
    order = (
        db.execute(
            select(Order)
            .where(Order.id == order.id)
            .options(
                joinedload(Order.student).joinedload(Student.user),
                joinedload(Order.outlet),
                joinedload(Order.payment),
                joinedload(Order.order_items).joinedload(OrderItem.menu_item),
            )
        )
        .scalars()
        .first()
    )
    return _serialize_order_for_portal(order)


@app.get("/api/admin-app/outlets")
def admin_app_outlets(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    return _outlet_metrics(db)


@app.post("/api/admin-app/outlets")
def admin_app_create_outlet(
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    name = str(payload.get("name", "")).strip()
    vendor_name = str(payload.get("vendorName", "")).strip() or "Campus Vendor"
    commission_rate = float(payload.get("commissionRate", 10))
    status_label = str(payload.get("status", "Active")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="Outlet name is required")

    outlet = Outlet(name=name, location=vendor_name, is_active=(status_label.lower() != "inactive"))
    db.add(outlet)
    db.flush()

    _write_setting(db, f"outlet_vendor_name_{outlet.id}", vendor_name)
    _write_setting(db, f"outlet_commission_rate_{outlet.id}", str(commission_rate))
    db.commit()
    return next((item for item in _outlet_metrics(db) if item["id"] == str(outlet.id)), None)


@app.put("/api/admin-app/outlets/{outlet_id}")
def admin_app_update_outlet(
    outlet_id: str,
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    try:
        parsed_id = int(outlet_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Outlet not found") from exc
    outlet = db.get(Outlet, parsed_id)
    if not outlet:
        raise HTTPException(status_code=404, detail="Outlet not found")

    if "name" in payload:
        outlet.name = str(payload["name"]).strip()
    if "vendorName" in payload:
        vendor_name = str(payload["vendorName"]).strip()
        outlet.location = vendor_name
        _write_setting(db, f"outlet_vendor_name_{outlet.id}", vendor_name)
    if "commissionRate" in payload:
        _write_setting(db, f"outlet_commission_rate_{outlet.id}", str(float(payload["commissionRate"])))
    if "status" in payload:
        outlet.is_active = str(payload["status"]).lower() != "inactive"

    db.commit()
    return next((item for item in _outlet_metrics(db) if item["id"] == str(outlet.id)), None)


@app.delete("/api/admin-app/outlets/{outlet_id}")
def admin_app_delete_outlet(
    outlet_id: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    try:
        parsed_id = int(outlet_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Outlet not found") from exc
    outlet = db.get(Outlet, parsed_id)
    if not outlet:
        raise HTTPException(status_code=404, detail="Outlet not found")
    db.delete(outlet)
    db.commit()
    return {"success": True}


@app.get("/api/admin-app/users")
def admin_app_users(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    users = db.execute(select(User).where(User.role != "student").order_by(User.created_at.desc())).scalars().all()
    return [_admin_portal_user(db, user) for user in users]


@app.post("/api/admin-app/users")
def admin_app_create_user(
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    portal_role = str(payload.get("role", PORTAL_ROLES["CAMPUS_ADMIN"])).upper()
    assigned_outlets = [str(item) for item in payload.get("assignedOutletIds", [])]
    status_label = "Inactive" if str(payload.get("status", "Active")).lower() == "inactive" else "Active"
    if not name or not email:
        raise HTTPException(status_code=400, detail="name and email are required")
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User email already exists")

    user = User(
        name=name,
        email=email,
        role=_model_role_for_portal(portal_role),
        password_hash=hash_password("Secure@123"),
    )
    db.add(user)
    db.flush()

    _write_setting(db, _status_key(user.id), status_label)
    _write_setting(db, _portal_role_key(user.id), portal_role)
    _write_setting(db, _assigned_outlets_key(user.id), json.dumps(assigned_outlets))
    db.commit()
    db.refresh(user)
    return _admin_portal_user(db, user)


@app.put("/api/admin-app/users/{user_id}")
def admin_app_update_user(
    user_id: str,
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    try:
        parsed_id = int(user_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    user = db.get(User, parsed_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if "name" in payload:
        user.name = str(payload["name"]).strip()
    if "email" in payload:
        email = str(payload["email"]).strip().lower()
        existing = db.execute(select(User).where(User.email == email, User.id != user.id)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="User email already exists")
        user.email = email
    if "role" in payload:
        portal_role = str(payload["role"]).upper()
        user.role = _model_role_for_portal(portal_role)
        _write_setting(db, _portal_role_key(user.id), portal_role)
    if "status" in payload:
        _write_setting(db, _status_key(user.id), "Inactive" if str(payload["status"]).lower() == "inactive" else "Active")
    if "assignedOutletIds" in payload:
        _write_setting(db, _assigned_outlets_key(user.id), json.dumps([str(item) for item in payload["assignedOutletIds"]]))

    db.commit()
    db.refresh(user)
    return _admin_portal_user(db, user)


@app.patch("/api/admin-app/users/{user_id}/toggle-status")
def admin_app_toggle_user(
    user_id: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    try:
        parsed_id = int(user_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    user = db.get(User, parsed_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    current = _portal_status_for_user(db, user.id)
    _write_setting(db, _status_key(user.id), "Inactive" if current == "Active" else "Active")
    db.commit()
    return _admin_portal_user(db, user)


def _portal_settings(db: Session):
    defaults = {
        "campusName": "Default Campus",
        "theme": "light",
        "taxRate": 5,
        "serviceChargeEnabled": True,
        "serviceChargeRate": 2,
        "logoName": "campus_logo.png",
    }
    values = {}
    for key, default in defaults.items():
        raw = _read_setting(db, f"portal_setting_{key}", None)
        if raw is None:
            values[key] = default
            continue
        if isinstance(default, bool):
            values[key] = str(raw).lower() == "true"
        elif isinstance(default, int):
            try:
                values[key] = int(float(raw))
            except Exception:
                values[key] = default
        else:
            values[key] = raw
    return values


@app.get("/api/admin-app/settings")
def admin_app_settings(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    return _portal_settings(db)


@app.put("/api/admin-app/settings")
def admin_app_update_settings(
    payload: dict,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    for key, value in payload.items():
        _write_setting(db, f"portal_setting_{key}", str(value))
    db.commit()
    return _portal_settings(db)


def _orders_in_days(orders: list[Order], days: int):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return [order for order in orders if order.created_at and order.created_at >= cutoff]


@app.get("/api/admin-app/executive-snapshot")
def admin_app_exec_snapshot(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    orders = (
        db.execute(
            select(Order)
            .options(joinedload(Order.outlet), joinedload(Order.student).joinedload(Student.user))
            .order_by(Order.created_at.desc())
        )
        .scalars()
        .all()
    )
    outlet_metrics = _outlet_metrics(db)
    distribution = []
    for status in ["Pending", "Preparing", "Ready", "Collected"]:
        distribution.append(
            {
                "name": status,
                "value": len([order for order in orders if _to_portal_order_status(order.status) == status]),
            }
        )

    today = datetime.now(timezone.utc).date()
    today_orders = [order for order in orders if order.created_at and order.created_at.date() == today]
    week_orders = _orders_in_days(orders, 7)
    month_orders = _orders_in_days(orders, 30)
    today_revenue = float(sum(float(order.total_amount or 0) for order in today_orders))
    week_revenue = float(sum(float(order.total_amount or 0) for order in week_orders))
    month_revenue = float(sum(float(order.total_amount or 0) for order in month_orders))
    total_orders = len(month_orders)

    revenue_series = []
    for idx in range(13, -1, -1):
        day = datetime.now(timezone.utc).date() - timedelta(days=idx)
        day_revenue = float(
            sum(float(order.total_amount or 0) for order in orders if order.created_at and order.created_at.date() == day)
        )
        revenue_series.append({"label": day.strftime("%d %b"), "revenue": day_revenue})

    heat_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    slots = [(7, 9), (9, 11), (11, 13), (13, 15), (15, 17), (17, 19), (19, 21)]
    heatmap = [{"day": day, "slots": [{"slot": f"{s:02d}-{e:02d}", "value": 0} for s, e in slots]} for day in heat_days]
    for order in orders:
        if not order.created_at:
            continue
        day_idx = (order.created_at.weekday()) % 7
        hour = order.created_at.hour
        for slot_idx, (start, end) in enumerate(slots):
            if start <= hour < end:
                heatmap[day_idx]["slots"][slot_idx]["value"] += 1
                break

    return {
        "totals": {
            "todayRevenue": today_revenue,
            "weekRevenue": week_revenue,
            "monthRevenue": month_revenue,
            "totalOrders": total_orders,
            "aov": round(month_revenue / total_orders, 2) if total_orders else 0,
            "activeOrders": len([order for order in orders if order.status in {"pending", "preparing", "ready"}]),
        },
        "revenueSeries": revenue_series,
        "distribution": distribution,
        "outletPerformance": outlet_metrics,
        "heatmap": heatmap,
    }


@app.get("/api/admin-app/reports")
def admin_app_reports(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
    range: str = Query(default="Week"),
):
    orders = db.execute(select(Order).options(joinedload(Order.outlet)).order_by(Order.created_at.desc())).scalars().all()
    days = 1 if range == "Today" else 7 if range == "Week" else 30
    current = _orders_in_days(orders, days)
    previous_cutoff_start = datetime.now(timezone.utc) - timedelta(days=days * 2)
    previous_cutoff_end = datetime.now(timezone.utc) - timedelta(days=days)
    previous = [
        row
        for row in orders
        if row.created_at and previous_cutoff_start <= row.created_at < previous_cutoff_end
    ]

    current_revenue = float(sum(float(order.total_amount or 0) for order in current))
    previous_revenue = float(sum(float(order.total_amount or 0) for order in previous))
    current_count = len(current)
    previous_count = len(previous)

    outlets = _outlet_metrics(db)
    revenue_by_outlet = []
    for outlet in outlets:
        outlet_id_int = int(outlet["id"])
        scoped = [order for order in current if order.outlet_id == outlet_id_int]
        revenue_by_outlet.append(
            {
                "outlet": outlet["name"],
                "revenue": float(sum(float(order.total_amount or 0) for order in scoped)),
                "orders": len(scoped),
            }
        )
    revenue_by_outlet.sort(key=lambda row: row["revenue"], reverse=True)

    payment_modes = ["UPI", "Card", "Cash", "Wallet"]
    payment_mode = []
    for mode in payment_modes:
        payment_mode.append(
            {
                "mode": mode,
                "value": len([order for order in current if _portal_payment_mode(order.payment_mode) == mode]),
            }
        )

    hourly_demand = []
    for i in range(8):
        start = 8 + i * 2
        end = start + 2
        hourly_demand.append(
            {
                "slot": f"{start:02d}:00-{end:02d}:00",
                "orders": len(
                    [
                        order
                        for order in current
                        if order.created_at and start <= order.created_at.hour < end
                    ]
                ),
            }
        )

    revenue_growth = 100 if previous_revenue == 0 else ((current_revenue - previous_revenue) / previous_revenue) * 100
    order_growth = 100 if previous_count == 0 else ((current_count - previous_count) / previous_count) * 100

    return {
        "range": range,
        "revenueByOutlet": revenue_by_outlet,
        "paymentMode": payment_mode,
        "hourlyDemand": hourly_demand,
        "trend": {"revenueGrowth": revenue_growth, "orderGrowth": order_growth},
        "periodTotals": {"revenueCurrent": current_revenue, "orderCurrent": current_count},
    }


@app.get("/api/admin-app/eod")
def admin_app_eod(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(_admin_app_user)],
):
    today = datetime.now(timezone.utc).date()
    rows = (
        db.execute(
            select(Order)
            .where(func.date(Order.created_at) == today)
            .options(joinedload(Order.student).joinedload(Student.user), joinedload(Order.outlet))
            .order_by(Order.created_at.desc())
        )
        .scalars()
        .all()
    )
    data = []
    for order in rows:
        data.append(
            {
                "orderId": str(order.id),
                "outlet": order.outlet.name if order.outlet else "Outlet",
                "student": order.student.user.name if order.student and order.student.user else "Student",
                "status": _to_portal_order_status(order.status),
                "paymentMode": _portal_payment_mode(order.payment_mode),
                "amount": float(order.total_amount or 0),
                "createdAt": order.created_at.isoformat() if order.created_at else None,
            }
        )
    return data
