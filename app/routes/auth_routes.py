from datetime import datetime, timezone
from secrets import token_urlsafe

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import current_user, get_jwt, jwt_required
from marshmallow import ValidationError

from app import db, limiter
from app.models import ROLE_STUDENT, Role, User
from app.schemas.auth import GoogleLoginSchema, LoginSchema, RegisterSchema
from app.services.audit_service import log_audit
from app.services.google_auth_service import verify_google_credential
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


def _auth_payload(user: User):
    tokens = create_user_tokens(user)
    return {"user": user.to_dict(), **tokens}


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

    log_audit(user.id, "user_register", "user", user.id)
    return jsonify(_auth_payload(user)), 201


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

    log_audit(user.id, "user_login", "user", user.id)
    return jsonify(_auth_payload(user)), 200


@auth_bp.post("/google")
@limiter.limit("20 per minute")
def google_login():
    payload = request.get_json(silent=True) or {}
    schema = GoogleLoginSchema()
    try:
        data = schema.load(payload)
    except ValidationError as err:
        raise APIError("Invalid Google login payload.", 400, "validation_error", err.messages)

    google_identity = verify_google_credential(
        data["credential"],
        current_app.config.get("GOOGLE_OAUTH_CLIENT_ID"),
    )

    user = User.query.filter_by(google_sub=google_identity["sub"]).first()
    created = False
    changed = False

    if user is None:
        user = User.query.filter_by(email=google_identity["email"]).first()
        if user and user.google_sub and user.google_sub != google_identity["sub"]:
            raise APIError(
                "This email is already linked to a different Google account.",
                409,
                "conflict",
            )

        if user is None:
            role = _get_role_by_name(ROLE_STUDENT)
            if not role:
                raise APIError("Role configuration missing.", 500, "configuration_error")

            user = User(
                name=google_identity["name"],
                email=google_identity["email"],
                role_id=role.id,
                auth_provider="google",
                google_sub=google_identity["sub"],
                avatar_url=google_identity["picture"],
            )
            user.set_password(token_urlsafe(32))
            db.session.add(user)
            created = True
            changed = True
        else:
            user.google_sub = google_identity["sub"]
            changed = True

    if not user.is_active:
        raise APIError("Account is disabled.", 403, "forbidden")

    if google_identity["picture"] and user.avatar_url != google_identity["picture"]:
        user.avatar_url = google_identity["picture"]
        changed = True

    if google_identity["name"] and user.name != google_identity["name"] and user.auth_provider == "google":
        user.name = google_identity["name"]
        changed = True

    if created:
        log_action = "user_register_google"
    else:
        log_action = "user_login_google"

    if changed:
        db.session.commit()

    log_audit(user.id, log_action, "user", user.id, {"provider": "google"})
    return jsonify(_auth_payload(user)), 201 if created else 200


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

    log_audit(user.id, "token_refresh", "user", user.id)
    return jsonify(create_user_tokens(user)), 200


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
