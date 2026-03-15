# Deployment Architecture

## Status

Live on Render. This document records the deployment configuration, boot path, and known failure patterns.

---

## Current Deployment Target

| Property | Value |
|---|---|
| Platform | [Render](https://render.com) |
| Service type | Web service (single service) |
| Runtime | Python |
| Config file | `infrastructure/render/render.yaml` |

---

## Single-Service Architecture

The production deployment runs **one Render web service** that serves both the FastAPI backend and the Next.js frontend UI:

```
Render Web Service
 ├── FastAPI backend
 │    ├── API routes           /api/v1/*
 │    ├── Swagger docs          /docs, /openapi.json
 │    └── Health endpoints      /health, /health/db
 └── Next.js frontend (pre-rendered HTML + static assets)
      ├── Root / redirect       /         → /dashboard
      ├── Login page            /login
      ├── Dashboard             /dashboard
      ├── Static chunks         /_next/static/*
      └── All other UI routes   /* (SPA fallback to nearest page)
```

### Route priority

FastAPI evaluates routes in registration order. The catch-all frontend handler is registered **last**, so API routes always take precedence:

| Route pattern | Handler |
|---|---|
| `/api/v1/*` | FastAPI API routers |
| `/docs`, `/openapi.json` | Swagger UI |
| `/health`, `/health/db` | Health check endpoints |
| `/_next/static/*` | Mounted Next.js compiled JS/CSS chunks |
| `/*` (catch-all) | Frontend HTML (page-specific or SPA fallback) |

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
cd frontend && npm ci && npm run build && cd .. && pip install -r requirements.txt && alembic upgrade head
```

The build sequence:
1. Install Node dependencies (`npm ci`).
2. Build the Next.js app (`npm run build`) — pre-rendered HTML lands in `frontend/.next/server/app/` and compiled static assets in `frontend/.next/static/`.
3. Install Python dependencies (`pip install -r requirements.txt`).
4. Apply all pending Alembic database migrations (`alembic upgrade head`).

### Start Command

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

`$PORT` is injected by Render at runtime. Do not hardcode the port.

---

## Frontend Build

The frontend (Next.js 15) is built using the standard `next build` command. The relevant output:

```
frontend/.next/
 ├── server/app/         # pre-rendered HTML files (one per static route)
 │    ├── index.html     # root / redirect to /dashboard
 │    ├── login.html
 │    ├── dashboard.html
 │    └── ...
 └── static/             # compiled JS/CSS chunks (served at /_next/static/)
      ├── chunks/
      └── css/
```

FastAPI mounts `frontend/.next/static/` at the URL prefix `/_next/static/` (efficient `StaticFiles` handler) and uses a wildcard catch-all route for all other browser paths:

1. Try exact HTML file: `/login` → `frontend/.next/server/app/login.html`
2. Try subdirectory index: `/login/` → `frontend/.next/server/app/login/index.html`
3. Serve parent page for dynamic routes: `/sales/123` → `frontend/.next/server/app/sales.html` (SPA loads and client-routes to the detail)
4. Root `index.html` as the ultimate SPA fallback

---

## Environment Variables

### Required (Production)

| Variable | Purpose | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |

`DATABASE_URL` on Render is sourced automatically from the attached managed database (`reach-developments-db`).

### Optional / Recommended

| Variable | Default | Purpose | Recommended Production Value |
|---|---|---|---|
| `APP_NAME` | `Reach Developments Station` | Application display name | *(leave as default)* |
| `APP_ENV` | `development` | Runtime environment label | `production` |
| `APP_DEBUG` | `false` | Debug mode flag | `false` |
| `LOG_LEVEL` | `INFO` | Logging verbosity | `INFO` |
| `API_V1_PREFIX` | `/api/v1` | API route prefix | `/api/v1` |
| `NEXT_PUBLIC_API_URL` | *(none)* | Frontend API base URL | `https://<service>.onrender.com/api/v1` |

### Informational Only

| Variable | Note |
|---|---|
| `APP_HOST` | Not read by uvicorn at runtime; Render controls binding via the start command |
| `APP_PORT` | Not read by uvicorn at runtime; Render injects `$PORT` |

See `.env.example` for the local development template.

---

## Deployment Flow

1. Push to the main branch triggers Render's auto-deploy.
2. Render executes the build command:
   - Step 1: `cd frontend && npm ci` — install Node dependencies.
   - Step 2: `npm run build && cd ..` — compile frontend; pre-rendered HTML → `frontend/.next/server/app/`, static chunks → `frontend/.next/static/`.
   - Step 3: `pip install -r requirements.txt` — install Python dependencies.
   - Step 4: `alembic upgrade head` — apply all pending database migrations.
3. Render executes the start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. The lifespan handler logs: `Starting <APP_NAME> [env=<APP_ENV>]`.
5. FastAPI mounts `frontend/.next/static/` at `/_next/static/`.
6. Health check at `GET /health` confirms liveness.
7. `GET /` serves the frontend `index.html` (which redirects the browser to `/dashboard`).

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

## Health Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Application health check (returns `{"status": "ok"}`) |
| `GET /health/db` | Database connectivity check |

> **Note:** `GET /` now serves the frontend HTML in production (when `frontend/.next/server/app/` exists). In development and test environments where the frontend is not built, it falls back to a lightweight JSON status payload for backward compatibility.
