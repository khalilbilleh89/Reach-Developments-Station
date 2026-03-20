# Performance Guidelines

> **PR-E7 — System Performance Pass**
>
> This document establishes the platform's performance baseline rules.  It is
> authoritative and must be consulted when adding or modifying backend queries,
> list endpoints, or frontend data-fetching calls.

---

## 1. Platform Architecture Reminder

The platform is a **single-service application** — no microservices, no Redis,
no background workers.  All performance work must stay within this constraint.

```
Render Web Service
 ├ FastAPI Backend
 ├ Static Next.js Frontend
 └ PostgreSQL Database
```

---

## 2. ORM Eager Loading Rules

### Why it matters

`RegistrationCaseResponse` embeds both `milestones` and `documents`.  Without
eager loading, accessing those relationships in a loop triggers **N+1 queries**:

```
1  SELECT * FROM registration_cases WHERE project_id = ?
N  SELECT * FROM registration_milestones WHERE registration_case_id = ?
N  SELECT * FROM registration_documents  WHERE registration_case_id = ?
```

With 50 cases this issues 101 queries instead of 3.

### Rule

> **Any repository list method whose results are serialised by a response schema
> that includes nested relationships MUST use `selectinload` or `joinedload`.**

### Pattern

```python
# ✅ Correct — one query per relationship, all cases at once
from sqlalchemy.orm import selectinload

def list_by_project(self, project_id: str, skip: int = 0, limit: int = 100):
    return (
        self.db.query(RegistrationCase)
        .options(
            selectinload(RegistrationCase.milestones),
            selectinload(RegistrationCase.documents),
        )
        .filter(RegistrationCase.project_id == project_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
```

```python
# ❌ Wrong — lazy-loads milestones/documents per case in the caller's loop
def list_by_project(self, project_id: str, skip: int = 0, limit: int = 100):
    return (
        self.db.query(RegistrationCase)
        .filter(RegistrationCase.project_id == project_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
```

### When to use each loader

| Loader | When to use |
|--------|-------------|
| `selectinload` | One-to-many relationships (milestones, documents, installments) |
| `joinedload` | Many-to-one relationships (buyer, contract, unit) |

### Hierarchy loading

`GET /projects` must **not** load the full `Project → Phase → Building → Floor → Unit`
hierarchy by default.  Hierarchy loading must be explicit (e.g., a dedicated
`/projects/{id}/hierarchy` endpoint).

---

## 3. Pagination Standards

### Rule

> **Every list endpoint must enforce `limit` and `skip` (offset) parameters with
> a sensible default and a hard maximum.**

### Standard defaults

```python
skip:  int = Query(default=0,   ge=0)
limit: int = Query(default=100, ge=1, le=500)
```

| Parameter | Default | Maximum |
|-----------|---------|---------|
| `limit`   | 100     | 500     |
| `skip`    | 0       | —       |

### Never allowed

```sql
-- No unguarded full-table scan
SELECT * FROM registration_cases WHERE project_id = ?
```

Always pair a `WHERE` clause with `.limit(n)`.

### Frontend caller rules

Frontend pages must request a **safe default limit** rather than the maximum:

```typescript
// ✅ Correct
listScopes({ limit: 100 })
listProjectCases(projectId, { limit: 100 })

// ❌ Wrong — requests too many rows for a portfolio page
listScopes({ limit: 500 })
```

Use `limit: 500` only for data-population flows (e.g., hierarchy tree builders
in the unit editor) where all records are genuinely needed in one request.

---

## 4. Dashboard Query Rules

Dashboard endpoints must aggregate data **in the database** using `SUM`,
`COUNT`, `GROUP BY`, not in Python loops.

```python
# ✅ Correct — single query with SQL aggregation
rows = (
    self.db.query(
        ConstructionCostItem.scope_id,
        func.sum(ConstructionCostItem.budget_amount).label("budget"),
    )
    .filter(ConstructionCostItem.scope_id.in_(scope_ids))
    .group_by(ConstructionCostItem.scope_id)
    .all()
)

# ❌ Wrong — loads all rows then sums in Python
items = self.db.query(ConstructionCostItem).filter(...).all()
total = sum(item.budget_amount for item in items)
```

---

## 5. API Payload Guidelines

| Pattern | Rule |
|---------|------|
| Nested one-to-many in list response | Use `selectinload`; cap list at 100 by default |
| Single-entity detail endpoint | OK to include all relationships |
| Summary/dashboard endpoint | Return aggregated scalars only, not raw rows |
| Registry case list | Includes milestones + documents; `selectinload` required |
| Finance summary | Return `SUM` result, not individual ledger rows |

---

## 6. Index Strategy

### Guiding principle

> Index every column that appears in a `WHERE`, `JOIN ON`, or `ORDER BY` clause
> of a query that runs on a hot path (list, count, dashboard aggregation).

### Index audit (current state after PR-E7)

| Table | Column(s) | Index name | Purpose |
|-------|-----------|------------|---------|
| `registration_cases` | `project_id` | `ix_registration_cases_project_id` | project-scoped list/count |
| `registration_cases` | `status` | `ix_registration_cases_status` | status filter queries |
| `registration_cases` | `(project_id, status)` | `ix_registration_cases_project_id_status` | composite; covers `count_completed_by_project` and `count_open_by_project` |
| `registration_cases` | `unit_id` | `ix_registration_cases_unit_id` | `get_active_by_unit` lookup |
| `registration_cases` | `sale_contract_id` | `ix_registration_cases_sale_contract_id` | contract-lookup |
| `registration_milestones` | `registration_case_id` | `ix_registration_milestones_case_id` | milestones-by-case |
| `registration_documents` | `registration_case_id` | `ix_registration_documents_case_id` | documents-by-case |
| `construction_scopes` | `project_id` | `ix_construction_scopes_project_id` | project-scoped scope list |
| `construction_milestones` | `scope_id` | `ix_construction_milestones_scope_id` | milestones-by-scope |
| `construction_progress_updates` | `milestone_id` | `ix_construction_progress_updates_milestone_id` | progress-by-milestone |
| `sales_contracts` | `unit_id` | `ix_sales_contracts_unit_id` | contract lookup by unit |
| `sales_contracts` | `buyer_id` | `ix_sales_contracts_buyer_id` | buyer contract history |
| `payment_schedules` | `contract_id` | `ix_payment_schedules_contract_id` | installments by contract |

### Adding new indexes

1. Add `index=True` to the model column (or add `Index(...)` to `__table_args__`).
2. Create a new Alembic migration that calls `op.create_index(...)`.
3. Add the index name to `TestIndexesExist._CRITICAL_INDEXES` in
   `tests/architecture/test_migration_integrity.py`.

---

## 7. Future Regression Prevention

The following architecture tests guard these rules:

| Test file | What it guards |
|-----------|----------------|
| `tests/architecture/test_query_efficiency.py` | N+1 prevention, pagination enforcement, index coverage |
| `tests/architecture/test_migration_integrity.py` | Index presence in ORM metadata and migrations |
| `tests/architecture/test_commercial_layer_contracts.py` | Domain boundary rules |

Run the full suite before merging any query or schema change:

```bash
pytest tests/architecture/
pytest
```
