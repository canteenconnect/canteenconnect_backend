# Codebase Guide

This guide is meant to make the FastAPI backend easier to navigate for future contributors.

## Runtime Entry Points

- `app/main.py`: creates the FastAPI application, CORS middleware, health routes, and OpenAPI tag metadata
- `app/services/bootstrap.py`: startup bootstrap for schema creation, seed roles, and initial admin setup

## Core Infrastructure

- `app/core/config.py`: environment-backed settings and CORS parsing
- `app/core/database.py`: SQLAlchemy engine, session factory, and database dependency
- `app/core/security.py`: password hashing, JWT signing, bearer token parsing, and OAuth2 scheme declaration

## API Layer

- `app/api/deps.py`: shared dependencies for DB sessions, current-user lookup, and role checks
- `app/api/routes/token.py`: canonical OAuth2 password-flow token endpoint
- `app/api/routes/auth.py`: registration, login alias, and current-user profile endpoint
- `app/api/routes/menu.py`: public menu reads plus admin-managed menu writes
- `app/api/routes/orders.py`: student ordering and operator status changes
- `app/api/routes/payments.py`: payment records tied to orders
- `app/api/routes/admin.py`: admin CRUD and operational views

## Domain Models

- `app/models/user.py`: user identity, role relationship, and account state
- `app/models/role.py`: normalized RBAC roles
- `app/models/outlet.py`: canteen outlets/campuses of operation
- `app/models/menu_item.py`: menu catalog entries by outlet
- `app/models/order.py`: order header and order lines
- `app/models/payment.py`: payment status tracking

## Schemas

The `app/schemas` package contains request and response models used to validate inbound payloads and document the API. The auth-related schemas include OpenAPI examples to improve Swagger usability.

## Services

- `app/services/auth.py`: registration, login lookup, token response creation, bootstrap roles, and initial admin seeding
- `app/services/orders.py`: order creation, pricing, stock updates, and payment linkage

## Tests

- `tests/test_api.py`: integration coverage for registration, OAuth2 login, RBAC, menu creation, ordering, and the OpenAPI OAuth2 declaration

## Deployment Files

- `Dockerfile`: container build for production
- `.github/workflows/ci.yml`: CI pipeline for lint, test, and image build
- `alembic.ini` and `migrations/`: schema migration support

## Where to Extend Next

- add refresh token rotation if sessions need longer-lived browser auth
- add audit logging and payment gateway webhooks
- add outlet-user assignment tables if operational access must be constrained per outlet
