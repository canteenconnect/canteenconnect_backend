from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError

from app import db, limiter
from app.schemas.profile import ProfileUpdateSchema
from app.services.audit_service import log_audit
from app.utils.api_error import APIError

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")


@profile_bp.get("/me")
@jwt_required()
def get_profile():
    if current_user is None:
        raise APIError("User not found.", 404, "not_found")
    return jsonify({"user": current_user.to_dict()}), 200


@profile_bp.put("/update")
@jwt_required()
@limiter.limit("10 per minute")
def update_profile():
    if current_user is None:
        raise APIError("User not found.", 404, "not_found")

    payload = request.get_json(silent=True) or {}
    schema = ProfileUpdateSchema()
    try:
        data = schema.load(payload)
    except ValidationError as err:
        raise APIError("Invalid profile payload.", 400, "validation_error", err.messages)

    for field in ["name", "phone", "roll_number", "department", "campus_id"]:
        if field in data:
            if field == "roll_number" and data[field]:
                existing = (
                    current_user.__class__.query.filter_by(roll_number=data[field])
                    .filter(current_user.__class__.id != current_user.id)
                    .first()
                )
                if existing:
                    raise APIError("roll_number already in use.", 409, "conflict")
            setattr(current_user, field, data[field])

    db.session.commit()
    log_audit(current_user.id, "profile_update", "user", current_user.id)
    return jsonify({"user": current_user.to_dict()}), 200
