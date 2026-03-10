# Canteen Backend Python Suite

Unified production backend stack using:
- FastAPI (core REST APIs)
- Flask + Flask-SocketIO (gateway + real-time events)
- Django (admin console)
- PostgreSQL

## Services
- Flask Gateway + Socket.IO: `http://localhost:8000`
- FastAPI Core: `http://localhost:8001`
- Django Admin: `http://localhost:8003/admin/`
- PostgreSQL: `localhost:5432`

## Quick Start
1. Copy `.env.example` to `.env` and update secrets.
2. Start stack:
   ```bash
   docker compose up --build -d
   ```
3. Health checks:
   - `GET http://localhost:8000/health`
   - `GET http://localhost:8001/health`
   - `GET http://localhost:8003/health`

## API Base
Use Flask gateway for all client API traffic:
- Base URL: `http://localhost:8000/api`

Supported route groups:
- `/auth/*`
- `/student/*`
- `/admin/*`
- `/dashboard/*`
- `/kitchen/*`
- Legacy admin compatibility: `/admin-app/*`

## Demo Credentials
Password for seeded users: `Secure@123`
- super.admin@smartcampus.io
- campus.admin@northbridge.edu
- kitchen.staff@northbridge.edu
- student1@northbridge.edu

Django admin credential is configured via:
- `DJANGO_ADMIN_USERNAME`
- `DJANGO_ADMIN_PASSWORD`