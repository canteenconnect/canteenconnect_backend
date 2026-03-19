# Frontend Authentication Flows

This document describes the live authentication flow used by the two frontend applications:

- Student portal: `canteenconnect-frontend`
- Admin portal: `canteen-admin`

Both applications authenticate against the same FastAPI backend and use the same OAuth2 password-based login flow.

## Shared Backend Endpoints

- `POST /token`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

## Token Model

Successful login returns:

```json
{
  "access_token": "<jwt-access-token>",
  "refresh_token": "<jwt-refresh-token>",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "student1",
    "email": "student1@example.com",
    "full_name": "Student One",
    "role": "student",
    "is_active": true,
    "created_at": "2026-03-19T10:00:00Z",
    "updated_at": "2026-03-19T10:00:00Z"
  }
}
```

The backend behavior is:

- access tokens are short-lived JWTs sent with `Authorization: Bearer ...`
- refresh tokens are persisted in the database
- each refresh call rotates the refresh token
- replaying an already-used refresh token revokes the whole refresh family
- logout blocklists the current access token and revokes the current refresh family

## Student Portal Flow

Source files:

- `client/src/hooks/use-auth.ts`
- `client/src/lib/api/client.ts`
- `client/src/lib/api/tokenStore.ts`

Flow:

1. The login form posts credentials to `POST /token`.
2. The frontend stores both `access_token` and `refresh_token` in local storage.
3. Authenticated axios requests attach the access token automatically.
4. If the backend returns `401`, the student axios client calls `POST /auth/refresh`.
5. On successful refresh, the frontend replaces both stored tokens and retries the failed request once.
6. On logout, the frontend calls `POST /auth/logout` with:
   - bearer access token in the `Authorization` header
   - refresh token in the JSON body
7. The frontend clears local storage after the logout request completes or fails.

## Admin Portal Flow

Source files:

- `src/services/apiClient.js`
- `src/services/mockApi.js`
- `src/store/useAuthStore.js`

Flow:

1. The admin login form posts credentials to `POST /token`.
2. The admin portal stores:
   - access token
   - refresh token
   - normalized admin user profile
3. Protected admin API requests use the stored access token.
4. If an admin request returns `401`, the client calls `POST /auth/refresh`.
5. If refresh succeeds, the admin portal updates the persisted token pair and retries the original request.
6. If refresh fails, the persisted auth cache is cleared and the user is redirected to `/login`.
7. On logout, the admin portal calls `POST /auth/logout` and then clears the persisted auth store.

## Role Expectations

Student portal accounts:

- `student`

Admin portal accounts:

- `admin`
- `super_admin`
- `campus_admin`
- `vendor_manager`
- `kitchen_staff`

The backend enforces RBAC independently of frontend routing. A user seeing an admin screen is not enough; every privileged API call is checked again on the server.

## Recommended Frontend Integration Rules

- Always prefer `POST /token` for username/email + password sign-in.
- Treat access tokens as disposable.
- Never try to reuse an older refresh token after a successful refresh.
- If `/auth/refresh` returns `401`, force a fresh login.
- Always call `/auth/logout` before clearing local session data when possible.
