from typing import Any

from flask import request

from app import db
from app.models import AuditLog


def log_audit(
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: dict[str, Any] | None = None,
):
    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
    audit = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=ip_address,
        details=details,
    )
    db.session.add(audit)
    db.session.commit()
