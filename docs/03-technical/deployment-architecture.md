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

## Required Environment Variables

The following environment variables must be set in the Render service dashboard (or equivalent):

| Variable | Purpose | Example |
|---|---|---|
| `APP_NAME` | Application display name | `Reach Developments Station` |
| `APP_ENV` | Runtime environment | `production` |
| `APP_DEBUG` | Debug mode flag | `false` |
| `APP_HOST` | Host binding (informational) | `0.0.0.0` |
| `APP_PORT` | Port (informational; Render injects `$PORT`) | `8000` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://...` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `API_V1_PREFIX` | API route prefix | `/api/v1` |

See `.env.example` for the local development template.

`DATABASE_URL` on Render is sourced automatically from the attached managed database (`reach-developments-db`).

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
| `GET /` | Lightweight root liveness check (returns app name, env, status) |
| `GET /health` | Application health check |
| `GET /health/db` | Database connectivity check |
