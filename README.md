# Canteen Management SaaS Backend

This repository contains a production-oriented FastAPI backend for a Canteen Management SaaS platform. It replaces the previous Flask and Django services with a single API that supports student authentication, admin operations, outlet and menu management, ordering, and payment tracking.

## Highlights

- FastAPI with automatic OpenAPI and Swagger docs at `/docs`
- OAuth2 password flow with JWT bearer tokens
- Argon2-backed password hashing through `pwdlib`
- Role-based access control for `admin` and `student`
- SQLAlchemy ORM models for users, outlets, menu items, orders, order items, and payments
- Alembic migrations for schema management
- Docker image for deployment
- GitHub Actions CI for linting, testing, and container builds

## Folder Structure

```text
canteen_backend/
+-- app/
¦   +-- api/
¦   ¦   +-- deps.py
¦   ¦   +-- routes/
¦   ¦       +-- admin.py
¦   ¦       +-- auth.py
¦   ¦       +-- menu.py
¦   ¦       +-- orders.py
¦   ¦       +-- payments.py
¦   ¦       +-- token.py
¦   +-- core/
¦   ¦   +-- config.py
¦   ¦   +-- database.py
¦   ¦   +-- security.py
¦   +-- models/
¦   +-- schemas/
¦   +-- services/
¦   +-- main.py
+-- migrations/
¦   +-- versions/
+-- tests/
+-- .github/workflows/ci.yml
+-- .dockerignore
+-- .env.example
+-- alembic.ini
+-- Dockerfile
+-- LICENSE
+-- README.md
+-- requirements.txt
```

## Environment Variables

Copy `.env.example` to `.env` and update the values.

```bash
cp .env.example .env
```

Important settings:

- `DATABASE_URL`: SQLAlchemy database URL. For PostgreSQL use `postgresql+psycopg://user:password@host:5432/dbname`
- `SECRET_KEY`: JWT signing key
- `CORS_ORIGINS`: comma-separated list of frontend origins
- `AUTO_CREATE_SCHEMA`: set to `true` only for local bootstrap convenience
- `INITIAL_ADMIN_*`: optional admin bootstrap credentials

## Local Development

1. Create a virtual environment.
2. Install dependencies.
3. Run migrations.
4. Start the API.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

## Authentication Flow

- `POST /auth/register` with JSON user payload to create a student account
- `POST /token` with `application/x-www-form-urlencoded` fields `username` and `password`
- Use the returned bearer token with `Authorization: Bearer <token>`

Swagger UI understands the OAuth2 password flow because the app exposes `/token` through `OAuth2PasswordBearer`.

## Core Endpoints

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `GET /menu`
- `POST /menu` admin only
- `POST /orders`
- `GET /orders/me`
- `PATCH /orders/{order_id}/status` admin only
- `POST /payments/orders/{order_id}`
- `GET /admin/users`
- `GET /admin/orders`
- `POST /admin/outlets`

## Docker

Build and run the service with Docker:

```bash
docker build -t canteen-backend .
docker run --env-file .env -p 8000:80 canteen-backend
```

## Testing and Quality

```bash
ruff check .
pytest
```

## Deployment Notes

- Run `alembic upgrade head` as part of your release process.
- Use a managed PostgreSQL instance in production.
- Keep `AUTO_CREATE_SCHEMA=false` in deployed environments.
- Rotate `SECRET_KEY` and bootstrap admin credentials through your secret manager.

