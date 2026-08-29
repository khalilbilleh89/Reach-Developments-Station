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

| Variable              | Production value                                  |
| --------------------- | ------------------------------------------------- |
| `APP_NAME`            | `reach-developments-station`                      |
| `APP_ENV`             | `production`                                      |
| `APP_DEBUG`           | `false` (startup fails if true in production)     |
| `DATABASE_URL`        | Render PostgreSQL **internal** connection URL     |
| `API_V1_PREFIX`       | `/api/v1`                                         |
| `SESSION_TTL_MINUTES` | `480` — optional; this is the default             |

That is the complete list. In particular there is **no** JWT secret, no token
signing key and no bootstrap admin password: sessions are opaque random tokens
stored as SHA-256 digests, and the first administrator is created interactively.

### Legacy V1 variables

The Render service may still carry variables from the demolished V1
application — a JWT algorithm and secret, an access-token expiry, a public
frontend API URL, an admin bootstrap credential. **This application reads none
of them.** Once the checks below pass, they can be removed from Render by hand.
Do not have the application delete them; application code does not change Render
configuration.

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

## 4. Creating the first administrator

The application does not create an administrator on startup. That would be a
hidden privileged write on every boot and would require a standing password in
the environment. It is a deliberate one-off act instead.

After the service is running:

1. Open the Render **Shell** for the web service.
2. Run:

   ```bash
   python -m app.modules.access.bootstrap_admin
   ```

3. Enter the email, display name and password when prompted. The password is
   read with `getpass`, so it is not echoed and does not enter shell history.
4. Sign in through the application. You will be required to replace the password
   immediately, which revokes the session and asks you to sign in again.

The command refuses to run a second time while an active System Administrator
exists: further users are created through the administration UI, where they are
audited. It writes one audit event with source `bootstrap` and no actor.

---

## 5. Post-merge verification

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
13. `GET /docs`, `/redoc` and `/api/v1/openapi.json` all return **404** in
    production. The schema enumerates every administrative endpoint, so it is
    withheld once real APIs exist.
14. The bootstrap command has been run and the first administrator can sign in.
15. The schema contains exactly the expected tables and nothing from V1:

    ```sql
    SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1;
    ```

    Expected after PR-MVP-04, and nothing else:

    ```text
    alembic_version, area_types, audit_events, buildings,
    country_approval_thresholds, country_packs, currencies,
    custom_field_definitions, custom_field_options, document_references, floors,
    inventory_sub_assets, land_parcel_custom_field_values, land_parcels,
    market_benchmarks, permit_status_events, permits, phases, planning_controls,
    pricing_area_rules, pricing_configurations, pricing_escalation_activations,
    pricing_escalation_rules, pricing_premium_rules,
    project_custom_field_values, projects, reference_values, roles, tax_rules,
    unit_area_schedules, unit_area_values, unit_custom_field_values,
    unit_price_components, unit_price_versions, unit_status_events, units,
    user_phase_access, user_project_access, user_roles, user_sessions, users
    ```

    ```sql
    SELECT version_num FROM alembic_version;   -- 0004_pricing
    SELECT count(*) FROM roles;                -- 11
    ```

    There must be no sales, reservation, payment-plan, receipt or unit-cost
    table yet: a sale arrives in PR-MVP-05 and cost in PR-MVP-08.

16. Existing project memberships still mean "the whole project":

    ```sql
    SELECT phase_scope, count(*) FROM user_project_access GROUP BY 1;
    ```

    Every row created before PR-MVP-03 must read `all`. A row reading `selected`
    would mean somebody's access silently narrowed on deploy.

17. No unit's pricing approval changed on deploy:

    ```sql
    SELECT pricing_approved, count(*) FROM units GROUP BY 1;
    ```

    `0004_pricing` writes no data, so this must read exactly what it read
    before. Every unit priced under PR-MVP-03 had `false` — nothing could set it
    — and it stays `false` until somebody activates a price.

Do not create another Render web service. Do not create another PostgreSQL
resource from a PR.

---

## 6. Rollback

`0004_pricing` creates eight tables and alters nothing; it moves no existing
data. `alembic downgrade 0003_inventory` drops exactly those tables, so a
rollback loses pricing entered after the deploy and nothing else — inventory,
land and permits are untouched, and `units.pricing_approved` keeps whatever
value it held. Take a database snapshot before deploying if any pricing has
already been loaded.

`0003_inventory` before it creates new tables and adds one column to
`user_project_access`, also without moving existing data; `alembic downgrade
0002_project_land_permits` drops the inventory tables and that column.

If a deploy fails:

1. Revert the PR on `main`.
2. Diagnose the infrastructure or configuration problem.
3. Do **not** restore V1 code into `main`.
4. Do **not** point the new PostgreSQL database at the old migration history.

The legacy history remains separate and untouched.

---

## 7. Local equivalent

```bash
# Build exactly what Render builds
./scripts/render-build.sh

# Run exactly what Render runs
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/reach_station"
./scripts/render-start.sh

# Create the first administrator (once, interactively)
python -m app.modules.access.bootstrap_admin
```
