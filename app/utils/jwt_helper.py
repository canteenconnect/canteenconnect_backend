from datetime import datetime, timezone

from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt

from app import db
from app.models import TokenBlocklist, User


def _user_claims(user: User):
    return {
        "role": user.role.name if user.role else None,
        "email": user.email,
        "name": user.name,
    }


def create_user_tokens(user: User):
    claims = _user_claims(user)
    access_token = create_access_token(identity=user.id, additional_claims=claims)
    refresh_token = create_refresh_token(identity=user.id, additional_claims=claims)
    return {"access_token": access_token, "refresh_token": refresh_token}


def revoke_token(jti: str, token_type: str, user_id: int, expires_at: datetime | None = None):
    if not jti:
        return
    db.session.add(
        TokenBlocklist(
            jti=jti,
            token_type=token_type,
            user_id=user_id,
            expires_at=expires_at,
        )
    )
    db.session.commit()


def revoke_current_token(user: User):
    jwt_payload = get_jwt()
    jti = jwt_payload.get("jti")
    token_type = jwt_payload.get("type", "access")
    exp = jwt_payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None
    revoke_token(jti, token_type, user.id, expires_at)
