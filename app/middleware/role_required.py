from functools import wraps

from flask import jsonify
from flask_jwt_extended import current_user, jwt_required


def role_required(*allowed_roles: str):
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            if current_user is None or current_user.role is None:
                return jsonify({"error": "unauthorized", "message": "Unauthorized"}), 401
            role_name = current_user.role.name
            if role_name not in allowed_roles:
                return (
                    jsonify(
                        {
                            "error": "forbidden",
                            "message": "You do not have permission to perform this action.",
                        }
                    ),
                    403,
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator
