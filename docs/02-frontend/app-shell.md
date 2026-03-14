# Frontend App Shell

## Status

Introduced in **PR-017**.

## Overview

The frontend application shell provides the structural foundation for the Reach Developments product experience. It transforms the existing backend API platform into a navigable product that operators can use day-to-day.

The shell is deliberately thin. It establishes the frame without embedding any domain logic, data fetching, or analytics. All future frontend PRs build on top of this foundation.

## Directory Structure

```
frontend/
├── next.config.js
├── package.json
├── tsconfig.json
├── jest.config.ts
└── src/
    ├── app/
    │   ├── layout.tsx                   # Root HTML layout
    │   ├── page.tsx                     # Root redirect → /dashboard
    │   ├── login/
    │   │   └── page.tsx                 # Login page (auth entry point)
    │   ├── (protected)/
    │   │   ├── layout.tsx               # Auth guard + AppShell wrapper
    │   │   ├── dashboard/page.tsx
    │   │   ├── projects/page.tsx
    │   │   ├── units-pricing/page.tsx
    │   │   ├── sales/page.tsx
    │   │   ├── payment-plans/page.tsx
    │   │   ├── collections/page.tsx
    │   │   ├── finance/page.tsx
    │   │   ├── registration/page.tsx
    │   │   ├── commission/page.tsx
    │   │   ├── cashflow/page.tsx
    │   │   └── settings/page.tsx
    │   └── __tests__/
    │       └── protected-routes.test.tsx
    ├── components/
    │   └── shell/
    │       ├── NavConfig.ts             # Central nav config (config-driven)
    │       ├── AppShell.tsx             # Primary shell frame
    │       ├── AppHeader.tsx            # Top bar
    │       ├── SidebarNav.tsx           # Left navigation
    │       ├── PageContainer.tsx        # Reusable page content wrapper
    │       └── __tests__/
    │           ├── AppShell.test.tsx
    │           └── SidebarNav.test.tsx
    ├── lib/
    │   ├── auth.ts                      # Token helpers + auth guard
    │   └── api-client.ts               # Shared API client wrapper
    └── styles/
        └── globals.css                  # Design tokens + global reset
```

## Shell Components

### `AppShell`

The top-level shell frame. Renders the sidebar, header, and content region. Manages the sidebar open/collapse state and the mobile overlay.

Props:

| Prop | Type | Description |
|---|---|---|
| `title` | `string` | Page title shown in the header |
| `breadcrumbs` | `Breadcrumb[]` | Reserved for future breadcrumb trail |
| `children` | `ReactNode` | Page content |

### `AppHeader`

Top application bar containing: app name, page title, search placeholder, notifications, user menu, and sign-out.

### `SidebarNav`

Config-driven navigation component. Reads from `NavConfig.ts` and renders grouped nav items with active route highlighting.

Supports:
- Active route highlighting via `aria-current="page"`
- Collapsed mode (icon-only)
- Grouped sections: `main` and `settings`
- Future role-based filtering via `futureRoleTags` in `NavConfig.ts`

### `PageContainer`

Reusable content wrapper for all protected pages. Provides consistent spacing, max-width, page title/subtitle, and an optional actions slot.

Props:

| Prop | Type | Description |
|---|---|---|
| `title` | `string` | Page heading |
| `subtitle` | `string` | Optional subheading |
| `actions` | `ReactNode` | Optional top-right slot |
| `children` | `ReactNode` | Page body content |

### `NavConfig.ts`

Central navigation configuration. All nav items are defined here with:

- `label` — display text
- `href` — route path
- `icon` — icon name key
- `section` — `main` or `settings`
- `requiresAuth` — auth requirement flag
- `futureRoleTags` — placeholder for future RBAC filtering

## Auth & API Client

### `src/lib/auth.ts`

Lightweight auth helpers:

- `setToken(token)` — stores access token in `localStorage`
- `getToken()` — retrieves stored token
- `clearToken()` — removes stored token
- `isAuthenticated()` — returns `true` if a token exists
- `requireAuth(redirectPath)` — redirects unauthenticated users
- `logout(redirectPath)` — clears token and redirects

The source of truth for authentication is the backend:
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

### `src/lib/api-client.ts`

Thin fetch wrapper:

- Reads base URL from `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000/api/v1`)
- Injects `Authorization: Bearer <token>` on every request
- Normalises error responses into `ApiError(status, message, body)`
- Methods: `get`, `post`, `put`, `patch`, `delete`

## Design Tokens

All design values are defined as CSS custom properties in `src/styles/globals.css`:

| Category | Examples |
|---|---|
| Spacing | `--space-1` through `--space-16` |
| Shell colours | `--color-sidebar-bg`, `--color-primary`, `--color-surface` |
| Typography | `--font-size-*`, `--font-weight-*` |
| Layout | `--sidebar-width`, `--header-height`, `--content-max-width` |
| Breakpoints | `--breakpoint-sm` through `--breakpoint-xl` |

## Running the Frontend

```bash
cd frontend
npm install
npm run dev        # development server at http://localhost:3000
npm run build      # production build
npm test           # run tests
npm run lint       # ESLint
```

Set `NEXT_PUBLIC_API_URL` in a `.env.local` file to point at the backend:

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## Navigation Sections

| Label | Route | Section |
|---|---|---|
| Dashboard | `/dashboard` | main |
| Projects | `/projects` | main |
| Units & Pricing | `/units-pricing` | main |
| Sales | `/sales` | main |
| Payment Plans | `/payment-plans` | main |
| Collections | `/collections` | main |
| Finance | `/finance` | main |
| Registration | `/registration` | main |
| Commission | `/commission` | main |
| Cashflow | `/cashflow` | main |
| Settings | `/settings` | settings |

## Non-Goals (PR-017)

This PR intentionally does NOT:

- Build full dashboard analytics widgets
- Implement project data tables
- Build finance, pricing, sales, or collections pages in depth
- Implement RBAC filtering (structure is in place for later)

## Follow-up PRs

| PR | Title |
|---|---|
| PR-018 | Project Dashboard UI |
| PR-019 | Units / Pricing UI |
| PR-020 | Sales Workflow UI |
| PR-021 | Payment Plans + Collections UI |
| PR-022 | Finance Dashboard UI |
