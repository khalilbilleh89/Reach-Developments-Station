# Deployment Architecture

## Status

Live on Render. This document records the deployment configuration, boot path, and known failure patterns.

---

## Current Deployment Target

| Property | Value |
|---|---|
| Platform | [Render](https://render.com) |
| Service type | Web service |
| Runtime | Python |
| Config file | `infrastructure/render/render.yaml` |

---

## Backend Service

### ASGI Entrypoint

The canonical application entrypoint is:

```text
app.main:app
```

This resolves to `app/main.py` → the `app` FastAPI instance. **Do not** use a root-level `main.py` or bare `main:app` — the `app/` package prefix is required.

### Build Command

```bash
pip install -r requirements.txt
```

### Start Command

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

`$PORT` is injected by Render at runtime. Do not hardcode the port.

---

## Environment Variables

### Required (Production)

These must be set in the Render service dashboard. The service will not function correctly in production without them.

| Variable | Purpose | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |

`DATABASE_URL` on Render is sourced automatically from the attached managed database (`reach-developments-db`).

### Optional / Recommended

These have application-level defaults (defined in `app/core/config.py`) and will work without being explicitly set. Setting them is recommended in production for clarity and correctness.

| Variable | Default | Purpose | Recommended Production Value |
|---|---|---|---|
| `APP_NAME` | `Reach Developments Station` | Application display name | *(leave as default)* |
| `APP_ENV` | `development` | Runtime environment label | `production` |
| `APP_DEBUG` | `false` | Debug mode flag | `false` |
| `LOG_LEVEL` | `INFO` | Logging verbosity | `INFO` |
| `API_V1_PREFIX` | `/api/v1` | API route prefix | `/api/v1` |

### Informational Only

These variables exist in config but are **not used** by the actual runtime binding. Render injects `$PORT` directly into the uvicorn start command. They do not need to be set in Render.

| Variable | Note |
|---|---|
| `APP_HOST` | Not read by uvicorn at runtime; Render controls binding via the start command |
| `APP_PORT` | Not read by uvicorn at runtime; Render injects `$PORT` |

See `.env.example` for the local development template.

---

## Deployment Flow

1. Push to the main branch triggers Render's auto-deploy.
2. Render executes the build command: `pip install -r requirements.txt`.
3. Render executes the start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. The lifespan handler logs: `Starting <APP_NAME> [env=<APP_ENV>]`.
5. Health check at `GET /health` confirms liveness.

---

## Known Startup Failure Pattern

### Error

```
Error loading ASGI app. Could not import module "main".
```

### Cause

Render (or uvicorn) was started with an incorrect module path:

```bash
# ❌ Wrong — no app/ package prefix
uvicorn main:app
```

### Fix

Use the fully-qualified package path:

```bash
# ✅ Correct
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

This is already set in `infrastructure/render/render.yaml`. Do not change it.

---

## Current Scope

- **Backend only** — API-first service
- **No frontend** — no UI service is deployed or expected in this phase
- **No worker services** — no background job queues or Redis in this phase

---

## Health Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /` | Lightweight root liveness check (returns app name and status; debug fields included when `APP_DEBUG=true`) |
| `GET /health` | Application health check |
| `GET /health/db` | Database connectivity check |
