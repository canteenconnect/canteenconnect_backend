# OAuth2 Password Flow

This backend uses FastAPI's OAuth2 password flow for first-party clients such as:

- Swagger UI
- the student portal
- the admin portal

## Endpoints

- `POST /token`
- `POST /auth/login`

Both endpoints accept `application/x-www-form-urlencoded` credentials and return the same JWT bearer token payload.

## Accepted Credentials

The form field is still named `username` because that is how `OAuth2PasswordRequestForm` is defined, but the backend accepts either:

- the user's username
- the user's email address

## Token Response

Successful authentication returns:

```json
{
  "access_token": "jwt-token",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin1",
    "email": "admin1@example.com",
    "full_name": "Admin One",
    "role": "admin",
    "is_active": true,
    "created_at": "2026-03-19T10:00:00Z",
    "updated_at": "2026-03-19T10:00:00Z"
  }
}
```

## Example Request

```bash
curl -X POST "http://localhost:8000/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin1&password=StrongPass123!"
```

You can also log in with email:

```bash
curl -X POST "http://localhost:8000/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin1@example.com&password=StrongPass123!"
```

## Using the Access Token

Pass the JWT in the `Authorization` header:

```bash
curl "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer <access_token>"
```

## Swagger UI

Open `/docs`, click `Authorize`, then paste the bearer token returned from `/token`.

The OpenAPI schema advertises the OAuth2 password flow with:

- scheme: `OAuth2PasswordBearer`
- token URL: `/token`

## Role Enforcement

Authentication only proves identity. Access to protected routes is enforced separately through RBAC dependencies in `app/api/deps.py`.

- `student` users can browse menu items and place orders
- `admin` users can manage outlets, users, and menu data
- additional operational roles such as `campus_admin`, `vendor_manager`, and `kitchen_staff` are also recognized by admin workflows
