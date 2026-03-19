# Startup and Bootstrap Behavior

## Overview

This document describes the application startup sequence, bootstrap/admin seed behavior, environment configuration, and expected log output for the Reach Developments Station backend.

---

## Startup Sequence

The application startup is orchestrated through FastAPI's `lifespan` context manager in `app/main.py`. The sequence is deterministic and executed in the following order:

### 1. Module-level initialization (import time)

Before the lifespan runs, Python executes module-level code when `app/main.py` is imported:

- All domain routers are imported and registered under `/api/v1`.
- The frontend static directory path is resolved (`frontend/out/_next/static`).
- If the Next.js compiled static asset directory exists, it is mounted at `/_next/static`.

These steps happen at import time, not inside the lifespan, because FastAPI requires mounts and router registrations to happen at app-creation time.

### 2. Lifespan startup

When the ASGI server starts handling requests, the `lifespan` function runs:

1. **Startup log** — emits `Starting <APP_NAME> [env=<APP_ENV>]`.
2. **Frontend build status log** — logs whether the HTML output directory (`frontend/out`) was found or is absent.
3. **Bootstrap decision** — evaluates whether to run admin seed based on:
   - `APP_ENV`: if `"test"`, bootstrap is skipped entirely.
   - `ADMIN_EMAIL` / `ADMIN_PASSWORD`: if either is absent, bootstrap is skipped.
   - If both conditions are satisfied (non-test env, both credentials set), bootstrap runs.
4. **Bootstrap execution** (if not skipped) — calls `seed_admin_user(db)` inside a managed database session.
5. **Startup-complete log** — emits `Startup complete: <APP_NAME> is ready.`

### 3. Request handling

After the lifespan startup completes, the ASGI application begins accepting requests normally.

### 4. Lifespan shutdown

When the server receives a shutdown signal:

1. **Shutdown log** — emits `Shutdown: <APP_NAME> stopping.`

---

## Bootstrap / Admin Seed Behavior

### Purpose

The bootstrap step seeds an initial administrator user account on a fresh deployment. This ensures the platform is immediately accessible via the admin credentials without manual intervention.

### Implementation

Bootstrap logic lives in `app/core/bootstrap.py` — the `seed_admin_user(db)` function.

### Idempotency

The function is safe to call on every application restart:

| Scenario | Behavior |
|---|---|
| User does not exist, role does not exist | Creates user, creates role, assigns role |
| User exists, role is not assigned | Assigns admin role to existing user |
| User exists, role already assigned | No-op, logs confirmation |
| Concurrent multi-worker startup race | `IntegrityError` is caught, rolls back, re-fetches — no crash |

### Skip conditions

Bootstrap is skipped (without error) in two scenarios:

| Condition | Log message |
|---|---|
| `APP_ENV=test` | `Bootstrap: skipped (test environment).` (DEBUG level) |
| `ADMIN_EMAIL` or `ADMIN_PASSWORD` not set | `Bootstrap: ADMIN_EMAIL / ADMIN_PASSWORD not configured — admin seed skipped.` |

### Failure behavior

If `seed_admin_user` raises an unexpected exception:

- The exception is logged at `ERROR` level with a full traceback.
- The application **continues starting** — bootstrap failure is non-fatal.
- The health endpoint (`/health`) will still return `200 ok`.

This ensures a deployment is not completely inaccessible because of a transient seed failure (e.g., momentary DB unavailability during startup).

---

## Environment Variables

### Required for production

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string. |
| `SECRET_KEY` | JWT signing key. **Must be overridden in production** — a `ValueError` is raised at startup if the default dev key is used in production. |

### Optional — admin seed

| Variable | Default | Description |
|---|---|---|
| `ADMIN_EMAIL` | `None` | Email address for the initial admin account. Bootstrap is skipped if unset. |
| `ADMIN_PASSWORD` | `None` | Password for the initial admin account. Bootstrap is skipped if unset. |

### Application behavior

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `Reach Developments Station` | Application name shown in logs and API schema. |
| `APP_ENV` | `development` | Environment name. Set to `"test"` to skip bootstrap. Set to `"production"` to enforce `SECRET_KEY` validation. |
| `APP_DEBUG` | `False` | Enables debug fields in the root JSON status payload. |
| `APP_HOST` | `0.0.0.0` | Bind address for uvicorn. |
| `APP_PORT` | `8000` | Bind port for uvicorn. |
| `LOG_LEVEL` | `INFO` | Log level. |
| `API_V1_PREFIX` | `/api/v1` | API route prefix. |

### JWT

| Variable | Default | Description |
|---|---|---|
| `JWT_ALGORITHM` | `HS256` | Algorithm for JWT token signing. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT access token lifetime in minutes. |

---

## Frontend Static Serving

FastAPI serves the Next.js static export directly. Two path patterns are relevant:

| Path | Source |
|---|---|
| `/_next/static/*` | Compiled JS/CSS chunks from `frontend/out/_next/static/`. Mounted as a `StaticFiles` directory if present. |
| `/*` (all other paths) | Served by the catch-all `serve_frontend` route from `frontend/out/`. |

### When the frontend build is absent

If `frontend/out` does not exist (development, CI, or test environments):

- `GET /` returns a JSON status payload: `{"app": "<APP_NAME>", "status": "running"}`.
- In debug mode (`APP_DEBUG=True`), the payload also includes `env` and `docs` fields.
- All API routes (`/api/v1/*`, `/health`, `/docs`) continue to work normally.
- This is not an error — it is an explicit fallback mode.

### Frontend resolution chain

For extensionless paths (SPA routes):

1. Exact HTML file: `/login` → `frontend/out/login.html`
2. Subdirectory index: `/login/` → `frontend/out/login/index.html`
3. Parent segment fallback: `/sales/123` → `frontend/out/sales.html`
4. Root index fallback: → `frontend/out/index.html`

For paths with file extensions (assets): served directly or 404 — never falls back to HTML.

---

## Health Endpoints

| Endpoint | Purpose | Response |
|---|---|---|
| `GET /health` | Liveness probe — confirms the ASGI app is running. | `200 {"status": "ok", "service": "..."}` |
| `GET /health/db` | Readiness probe — confirms database connectivity. | `200 {"status": "ok", "database": "reachable"}` or `503 {"status": "error", "database": "unreachable"}` |

The `/health` endpoint does not check database connectivity. It always returns `200` as long as the ASGI process is alive. Use `/health/db` to verify the database is reachable.

---

## Expected Startup Log Output

A normal startup with frontend build absent and admin seed enabled:

```
INFO  Starting Reach Developments Station [env=production]
INFO  Startup: frontend build not found at 'frontend/out' — JSON status fallback active.
INFO  Bootstrap: admin user 'admin@example.com' created.
INFO  Bootstrap: admin role confirmed for 'admin@example.com'.
INFO  Startup complete: Reach Developments Station is ready.
```

A normal startup with frontend build present and admin already seeded:

```
INFO  Starting Reach Developments Station [env=production]
INFO  Startup: frontend build found at 'frontend/out'.
INFO  Bootstrap: admin user 'admin@example.com' already exists — ensuring role assignment.
INFO  Bootstrap: admin role confirmed for 'admin@example.com'.
INFO  Startup complete: Reach Developments Station is ready.
```

A startup with bootstrap disabled (no credentials configured):

```
INFO  Starting Reach Developments Station [env=production]
INFO  Startup: frontend build found at 'frontend/out'.
INFO  Bootstrap: ADMIN_EMAIL / ADMIN_PASSWORD not configured — admin seed skipped.
INFO  Startup complete: Reach Developments Station is ready.
```

A startup with a bootstrap failure (transient DB error):

```
INFO  Starting Reach Developments Station [env=production]
INFO  Startup: frontend build found at 'frontend/out'.
ERROR Bootstrap: admin seed failed — application startup continues.
      Traceback (most recent call last):
        ...
INFO  Startup complete: Reach Developments Station is ready.
```

---

## Local vs Deployed Startup Notes

| Concern | Local Development | Deployed (Render) |
|---|---|---|
| `APP_ENV` | `development` (default) | Set to `production` via env var |
| `SECRET_KEY` | Dev default allowed | **Must** be overridden |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Optional — set in `.env` to seed local admin | Set as Render env vars |
| Database | PostgreSQL (or override via `DATABASE_URL`) | Render managed PostgreSQL |
| Frontend | Run Next.js dev server separately or build `frontend/out` | Built in Render build command |
| Bootstrap skip | Not skipped (unless `APP_ENV=test`) | Runs once, idempotent on restart |

### Running tests

The test suite sets `APP_ENV=test` (via `conftest.py` test database setup), which skips the bootstrap path entirely. Tests that need bootstrap behavior call `seed_admin_user` directly with an injected in-memory session.

---

## Idempotency Guarantees

Bootstrap is designed to be called on every application restart without side effects:

- **No duplicate users** — `ADMIN_EMAIL` uniqueness is enforced at the database level.
- **No duplicate roles** — Role name uniqueness is enforced; concurrent creation races are handled via rollback-and-re-fetch.
- **No duplicate role assignments** — `assign_role` is idempotent.
- **No data mutation** — An existing admin user's email or password is never modified by bootstrap.

---

## Related Files

| File | Purpose |
|---|---|
| `app/main.py` | Application entrypoint, lifespan, router registration, static frontend serving |
| `app/core/bootstrap.py` | Admin seed logic — `seed_admin_user` |
| `app/core/config.py` | Environment/settings loading via pydantic-settings |
| `app/core/database.py` | SQLAlchemy engine, `SessionLocal`, `check_db_connection` |
| `tests/architecture/test_startup_bootstrap.py` | Startup/bootstrap hardening tests |
| `tests/auth/test_bootstrap.py` | Unit tests for `seed_admin_user` |
| `tests/test_runtime_boot.py` | Boot smoke tests — app import, root/health endpoint |
| `tests/test_health.py` | Health endpoint unit tests |
