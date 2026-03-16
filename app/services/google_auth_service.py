from __future__ import annotations

from google.auth.transport.requests import Request
from google.oauth2 import id_token

from app.utils.api_error import APIError


def verify_google_credential(credential: str, client_id: str) -> dict:
    if not credential:
        raise APIError("Google credential is required.", 400, "validation_error")
    if not client_id:
        raise APIError("Google OAuth is not configured.", 500, "configuration_error")

    try:
        token_data = id_token.verify_oauth2_token(
            credential,
            Request(),
            client_id,
            clock_skew_in_seconds=10,
        )
    except ValueError as exc:
        raise APIError("Google token verification failed.", 401, "authentication_failed") from exc

    email = str(token_data.get("email") or "").strip().lower()
    sub = str(token_data.get("sub") or "").strip()
    email_verified = bool(token_data.get("email_verified"))

    if not sub or not email:
        raise APIError("Google account details are incomplete.", 400, "validation_error")
    if not email_verified:
        raise APIError("Google account email is not verified.", 403, "forbidden")

    return {
        "sub": sub,
        "email": email,
        "name": str(token_data.get("name") or email.split("@")[0]).strip(),
        "picture": str(token_data.get("picture") or "").strip() or None,
        "given_name": str(token_data.get("given_name") or "").strip() or None,
        "family_name": str(token_data.get("family_name") or "").strip() or None,
    }
