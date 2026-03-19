"""Integration tests covering auth, RBAC, and ordering flows."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.schemas.user import UserCreate
from app.services.auth import create_user


def register_student(client: TestClient) -> None:
    """Register a baseline student user for tests."""

    response = client.post(
        "/auth/register",
        json={
            "username": "student1",
            "email": "student1@example.com",
            "full_name": "Student One",
            "password": "StrongPass123!",
            "role": "student",
        },
    )
    assert response.status_code == 201, response.text


def login(client: TestClient, username: str, password: str) -> str:
    """Authenticate a user and return the bearer token."""

    payload = login_payload(client, username, password)
    return payload["access_token"]


def login_payload(client: TestClient, username: str, password: str) -> dict:
    """Authenticate a user and return the full token payload."""

    response = client.post(
        "/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def login_via_auth_route(client: TestClient, identifier: str, password: str) -> dict:
    """Authenticate through `/auth/login` and return the full token payload."""

    response = client.post(
        "/auth/login",
        data={"username": identifier, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_admin(client: TestClient, db_session_factory) -> str:
    """Create an admin user directly through the service layer."""

    with db_session_factory() as db:
        create_user(
            db,
            UserCreate(
                username="admin1",
                email="admin1@example.com",
                full_name="Admin One",
                password="StrongPass123!",
                role="admin",
            ),
            allow_admin_role=True,
        )

    return login(client, "admin1", "StrongPass123!")


def test_register_login_and_me(client: TestClient) -> None:
    """A student can register, log in, and fetch their profile."""

    register_student(client)
    token = login(client, "student1", "StrongPass123!")

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "student1"
    assert body["role"] == "student"


def test_oauth2_login_accepts_email_and_auth_alias(client: TestClient) -> None:
    """OAuth2 login works with email identifiers on both auth endpoints."""

    register_student(client)

    token = login(client, "student1@example.com", "StrongPass123!")
    assert isinstance(token, str)
    assert token

    auth_payload = login_via_auth_route(client, "student1@example.com", "StrongPass123!")
    assert auth_payload["token_type"] == "bearer"
    assert isinstance(auth_payload["refresh_token"], str)
    assert auth_payload["refresh_token"]
    assert auth_payload["user"]["email"] == "student1@example.com"
    assert auth_payload["user"]["role"] == "student"


def test_openapi_exposes_oauth2_password_flow(client: TestClient) -> None:
    """Generated OpenAPI spec advertises the OAuth2 password flow."""

    response = client.get("/openapi.json")
    assert response.status_code == 200, response.text

    schema = response.json()
    oauth_scheme = schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]
    assert oauth_scheme["type"] == "oauth2"
    assert oauth_scheme["flows"]["password"]["tokenUrl"] == "/token"


def test_refresh_rotation_and_reuse_revocation(client: TestClient) -> None:
    """Refresh tokens rotate once and replayed tokens revoke the family."""

    register_student(client)
    first_session = login_payload(client, "student1", "StrongPass123!")

    refresh_response = client.post(
        "/auth/refresh",
        json={"refresh_token": first_session["refresh_token"]},
    )
    assert refresh_response.status_code == 200, refresh_response.text
    second_session = refresh_response.json()
    assert second_session["access_token"] != first_session["access_token"]
    assert second_session["refresh_token"] != first_session["refresh_token"]

    replay_response = client.post(
        "/auth/refresh",
        json={"refresh_token": first_session["refresh_token"]},
    )
    assert replay_response.status_code == 401, replay_response.text

    revoked_family_response = client.post(
        "/auth/refresh",
        json={"refresh_token": second_session["refresh_token"]},
    )
    assert revoked_family_response.status_code == 401, revoked_family_response.text


def test_logout_revokes_current_access_and_refresh_tokens(client: TestClient) -> None:
    """Logging out revokes the active access token and refresh family."""

    register_student(client)
    session = login_payload(client, "student1", "StrongPass123!")
    access_token = session["access_token"]
    refresh_token = session["refresh_token"]

    logout_response = client.post(
        "/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_response.status_code == 204, logout_response.text

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 401, me_response.text

    refresh_response = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 401, refresh_response.text


def test_student_cannot_manage_menu(client: TestClient) -> None:
    """Students are blocked from admin-only menu management routes."""

    register_student(client)
    token = login(client, "student1", "StrongPass123!")

    response = client.post(
        "/menu",
        json={
            "outlet_id": 1,
            "name": "Veg Fried Rice",
            "description": "Fresh wok-tossed rice",
            "price": "99.00",
            "stock_quantity": 10,
            "is_available": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_admin_can_create_outlet_menu_and_student_can_order(
    client: TestClient,
    db_session_factory,
) -> None:
    """End-to-end order flow works across admin and student roles."""

    admin_token = create_admin(client, db_session_factory)
    register_student(client)
    student_token = login(client, "student1", "StrongPass123!")

    outlet_response = client.post(
        "/admin/outlets",
        json={"name": "Main Block", "location": "Campus Center", "is_active": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert outlet_response.status_code == 201, outlet_response.text
    outlet_id = outlet_response.json()["id"]

    menu_response = client.post(
        "/menu",
        json={
            "outlet_id": outlet_id,
            "name": "Veg Fried Rice",
            "description": "Fresh wok-tossed rice",
            "price": "99.00",
            "stock_quantity": 10,
            "is_available": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert menu_response.status_code == 201, menu_response.text
    menu_item_id = menu_response.json()["id"]

    order_response = client.post(
        "/orders",
        json={
            "outlet_id": outlet_id,
            "payment_method": "upi",
            "items": [{"menu_item_id": menu_item_id, "quantity": 2}],
        },
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert order_response.status_code == 201, order_response.text
    order = order_response.json()
    assert order["total_amount"] == "198.00"
    assert order["status"] == "pending"

    payment_response = client.post(
        f"/payments/orders/{order['id']}",
        json={"provider": "upi", "transaction_reference": "TXN123", "status": "paid"},
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert payment_response.status_code == 201, payment_response.text

    status_response = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "preparing"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["status"] == "preparing"

