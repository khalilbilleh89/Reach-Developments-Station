# Deployment — Reach Developments Station

MVP 1.0 runs as **one Render web service** connected to **one Render PostgreSQL
database**. There is no second service, no separate frontend host, and no
infrastructure created from application code.

---

## 1. The important change from the legacy deployment

**The build stage must never require a database connection.**

Previously, Alembic ran during build. A transient database problem therefore
failed the entire source build — a configuration incident presented as a code
failure.

Responsibilities are now separated:

| Stage | Script                    | Does                                                     | Needs PostgreSQL |
| ----- | ------------------------- | -------------------------------------------------------- | ---------------- |
| Build | `scripts/render-build.sh` | install backend deps, install frontend deps, build export | **No**           |
| Start | `scripts/render-start.sh` | `alembic upgrade head`, then `exec uvicorn`               | **Yes**          |

A database outage is now a **runtime / deployment-readiness failure**, not a
source-build failure. Render keeps the previous healthy instance serving while a
failing deploy is investigated.

---

## 2. Render service configuration

| Setting        | Value                                                    |
| -------------- | -------------------------------------------------------- |
| Repository     | this GitHub repository                                    |
| Branch         | `main`                                                    |
| Runtime        | Python 3.13 (pinned by `.python-version`)                 |
| Build command  | `./scripts/render-build.sh`                               |
| Start command  | `./scripts/render-start.sh`                               |
| Health check   | `/api/v1/health/ready`                                    |

### Runtime pinning

Do not rely on Render's current default language versions.

- **Python** — `.python-version` contains `3.13`. Render reads this file. Set the
  `PYTHON_VERSION` environment variable to the same value if the service was
  created before the file existed.
- **Node.js** — `.nvmrc` contains `22`. Set `NODE_VERSION` to `22` if Render does
  not pick up `.nvmrc` for this service.

### Environment variables

| Variable         | Production value                                     |
| ---------------- | ---------------------------------------------------- |
| `APP_NAME`       | `reach-developments-station`                         |
| `APP_ENV`        | `production`                                         |
| `APP_DEBUG`      | `false` (startup fails if true in production)         |
| `DATABASE_URL`   | Render PostgreSQL **internal** connection URL         |
| `API_V1_PREFIX`  | `/api/v1`                                             |

Use the **internal** connection URL whenever the web service and the database
are in the same Render region: it is faster and never leaves Render's network.

`postgres://` and `postgresql://` URLs are both accepted exactly as Render emits
them. `app/core/config.py` applies the Psycopg 3 driver centrally — never edit
the value by hand to add `+psycopg`.

No production secret is ever committed. `.env.example` holds placeholders only.

---

## 3. Request routing in production

```text
/api/v1/*   ->  FastAPI
/*          ->  static Next.js export from frontend/out
```

API routes are registered before the static mount, so no static file can shadow
the API namespace. The Next.js export uses `trailingSlash: true`, which
Starlette's `StaticFiles(..., html=True)` resolves directly — there is no custom
SPA fallback router to maintain.

---

## 4. Post-merge verification

After merging to `main`, do not assume the deploy succeeded. Verify:

1. The existing Render service still points at this GitHub repository.
2. The Render branch is `main`.
3. `DATABASE_URL` points at the new Render PostgreSQL database.
4. `DATABASE_URL` uses the internal connection URL where applicable.
5. The build command invokes `scripts/render-build.sh`.
6. The start command invokes `scripts/render-start.sh`.
7. The build succeeds **without** a database connection.
8. The startup migration succeeds (`alembic upgrade head` in the deploy log).
9. `GET /api/v1/health/live` returns `200`.
10. `GET /api/v1/health/ready` returns `200`.
11. The root URL serves the new frontend.
12. No old V1 routes or UI are reachable.

Do not create another Render web service. Do not create another PostgreSQL
resource from a PR.

---

## 5. Rollback

PR-MVP-00 contains no business data migration, so rollback risk is low.

If a deploy fails:

1. Revert the PR on `main`.
2. Diagnose the infrastructure or configuration problem.
3. Do **not** restore V1 code into `main`.
4. Do **not** point the new PostgreSQL database at the old migration history.

The legacy history remains separate and untouched.

---

## 6. Local equivalent

```bash
# Build exactly what Render builds
./scripts/render-build.sh

# Run exactly what Render runs
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/reach_station"
./scripts/render-start.sh
```
