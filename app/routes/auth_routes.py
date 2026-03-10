from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, get_jwt, jwt_required
from marshmallow import ValidationError

from app import db, limiter
from app.models import ROLE_STUDENT, Role, User
from app.schemas.auth import LoginSchema, RegisterSchema
from app.services.audit_service import log_audit
from app.utils.api_error import APIError
from app.utils.jwt_helper import create_user_tokens, revoke_current_token, revoke_token

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _get_role_by_name(role_name: str):
    role = Role.query.filter_by(name=role_name).first()
    if role:
        return role
    role = Role(name=role_name, description=f"System role: {role_name}")
    db.session.add(role)
    db.session.commit()
    return role


@auth_bp.post("/register")
@limiter.limit("10 per minute")
def register():
    payload = request.get_json(silent=True) or {}
    schema = RegisterSchema()
    try:
        data = schema.load(payload)
    except ValidationError as err:
        raise APIError("Invalid registration payload.", 400, "validation_error", err.messages)

    role_name = str(data.get("role") or ROLE_STUDENT).upper()
    if role_name != ROLE_STUDENT:
        raise APIError("Only student registration is supported.", 403, "forbidden")

    if User.query.filter_by(email=data["email"].lower()).first():
        raise APIError("Email already registered.", 409, "conflict")
    if data.get("roll_number") and User.query.filter_by(roll_number=data["roll_number"]).first():
        raise APIError("roll_number already registered.", 409, "conflict")

    role = _get_role_by_name(role_name)
    if not role:
        raise APIError("Role configuration missing.", 500, "configuration_error")

    user = User(
        name=data["name"].strip(),
        email=data["email"].lower(),
        phone=data.get("phone"),
        role_id=role.id,
        campus_id=data.get("campus_id"),
        roll_number=data.get("roll_number"),
        department=data.get("department"),
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    tokens = create_user_tokens(user)
    log_audit(user.id, "user_register", "user", user.id)
    return jsonify({"user": user.to_dict(), **tokens}), 201


@auth_bp.post("/login")
@limiter.limit("20 per minute")
def login():
    payload = request.get_json(silent=True) or {}
    schema = LoginSchema()
    try:
        data = schema.load(payload)
    except ValidationError as err:
        raise APIError("Invalid login payload.", 400, "validation_error", err.messages)

    user = User.query.filter_by(email=data["email"].lower()).first()
    if not user or not user.check_password(data["password"]):
        raise APIError("Invalid credentials.", 401, "authentication_failed")
    if not user.is_active:
        raise APIError("Account is disabled.", 403, "forbidden")

    tokens = create_user_tokens(user)
    log_audit(user.id, "user_login", "user", user.id)
    return jsonify({"user": user.to_dict(), **tokens}), 200


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    jwt_payload = get_jwt()
    identity = jwt_payload.get("sub")
    user = User.query.get(int(identity)) if identity is not None else None
    if not user:
        raise APIError("User not found.", 404, "not_found")

    jti = jwt_payload.get("jti")
    exp = jwt_payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None
    revoke_token(jti, "refresh", user.id, expires_at)

    tokens = create_user_tokens(user)
    log_audit(user.id, "token_refresh", "user", user.id)
    return jsonify(tokens), 200


@auth_bp.post("/logout")
@jwt_required()
def logout():
    if current_user is None:
        raise APIError("User not found.", 404, "not_found")
    revoke_current_token(current_user)
    jwt_payload = get_jwt()
    identity = jwt_payload.get("sub")
    if identity:
        log_audit(int(identity), "user_logout", "user", int(identity))
    return jsonify({"message": "Logged out successfully."}), 200
