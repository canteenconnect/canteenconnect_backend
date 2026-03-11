from flask import Flask, jsonify
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from config import get_config

db = SQLAlchemy()
bcrypt = Bcrypt()
jwt = JWTManager()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per minute"])


def _register_error_handlers(app: Flask):
    from app.utils.api_error import APIError

    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        payload = {
            "error": error.name.replace(" ", "_").lower(),
            "message": error.description,
        }
        return jsonify(payload), error.code

    @app.errorhandler(SQLAlchemyError)
    def handle_db_error(error: SQLAlchemyError):
        app.logger.exception("Database error: %s", error)
        db.session.rollback()
        return (
            jsonify({"error": "database_error", "message": "A database error occurred."}),
            500,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        app.logger.exception("Unhandled error: %s", error)
        return (
            jsonify({"error": "internal_server_error", "message": "An unexpected error occurred."}),
            500,
        )


def _register_jwt_callbacks(app: Flask):
    from app.models import TokenBlocklist, User

    @jwt.unauthorized_loader
    def unauthorized_callback(reason: str):
        return jsonify({"error": "unauthorized", "message": reason}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(reason: str):
        return jsonify({"error": "invalid_token", "message": reason}), 422

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "token_expired", "message": "Token has expired."}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "token_revoked", "message": "Token has been revoked."}), 401

    @jwt.user_identity_loader
    def identity_loader(user_id):
        return str(user_id)

    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        identity = jwt_data.get("sub")
        if identity is None:
            return None
        return User.query.get(int(identity))

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(_jwt_header, jwt_payload):
        jti = jwt_payload.get("jti")
        if not jti:
            return True
        return TokenBlocklist.query.filter_by(jti=jti).first() is not None


def _register_security_headers(app: Flask):
    @app.after_request
    def apply_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'",
        )
        return response


def _register_blueprints(app: Flask):
    from app.routes.admin_routes import admin_bp
    from app.routes.auth_routes import auth_bp
    from app.routes.compat_routes import compat_bp
    from app.routes.payment_routes import payment_bp
    from app.routes.profile_routes import profile_bp
    from app.routes.student_routes import student_bp
    from app.routes.vendor_routes import vendor_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(vendor_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(compat_bp)

    # Backward-compatible /api prefix for existing clients.
    app.register_blueprint(auth_bp, url_prefix="/api", name_prefix="api")
    app.register_blueprint(profile_bp, url_prefix="/api", name_prefix="api")
    app.register_blueprint(student_bp, url_prefix="/api", name_prefix="api")
    app.register_blueprint(vendor_bp, url_prefix="/api", name_prefix="api")
    app.register_blueprint(admin_bp, url_prefix="/api", name_prefix="api")
    app.register_blueprint(payment_bp, url_prefix="/api", name_prefix="api")


def create_app(config_name: str | None = None):
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    CORS(
        app,
        resources={r"/*": {"origins": app.config.get("CORS_ORIGINS")}},
        supports_credentials=True,
    )

    from app import models  # noqa: F401

    _register_security_headers(app)
    _register_error_handlers(app)
    _register_jwt_callbacks(app)
    _register_blueprints(app)

    from app.cli import create_superadmin, seed_roles

    app.cli.add_command(seed_roles)
    app.cli.add_command(create_superadmin)

    @app.get("/")
    def index():
        return (
            jsonify(
                {
                    "status": "ok",
                    "message": "CanteenConnect API is running.",
                    "health": "/health",
                    "docs": "Not available",
                }
            ),
            200,
        )

    @app.get("/health")
    def health_check():
        return jsonify({"status": "ok"}), 200

    @app.get("/rate-limit")
    @limiter.limit("10 per minute")
    def rate_limit_check():
        return jsonify({"status": "ok"}), 200

    return app
