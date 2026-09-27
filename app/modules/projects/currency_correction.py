"""One controlled, atomic correction of a project's mistaken base denomination.

This is deliberately a reviewed cross-domain maintenance operation. Every table
that stores its own project-scoped currency is named here; amounts are untouched.
New currency-bearing tables must be added to this list before this operation is
considered safe for them. Each changed row receives an audit event.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.db.base import Base
from app.modules.audit.service import record_event

# Static identifiers only. No name in this map comes from a request.
CURRENCY_COLUMNS: dict[str, tuple[str, ...]] = {
    "cashflow_forecast_versions": ("currency_id",),
    "cashflow_development_movements": ("currency_id",),
    "cashflow_financing_movements": ("currency_id",),
    "reservations": ("currency_id", "deposit_currency_id"),
    "sale_contracts": ("currency_id",),
    "sale_contract_tax_lines": ("currency_id",),
    "sale_legal_events": ("currency_id",),
    "collection_receipts": ("currency_id",),
    "collection_refunds": ("currency_id",),
    "payment_plan_versions": ("currency_id",),
    "pricing_configurations": ("pricing_currency_id",),
    "market_benchmarks": ("currency_id",),
    "unit_price_versions": ("currency_id",),
    "construction_budget_versions": ("currency_id",),
    "construction_contracts": ("currency_id",),
    "construction_payments": ("currency_id",),
    "construction_forecast_versions": ("currency_id",),
    "unit_economics_allocation_versions": ("currency_id",),
    "unit_economics_unit_costs": ("currency_id",),
    "ue_current_cost_settings": ("currency_id",),
    "commission_grants": ("currency_id",),
}


def require_complete_currency_map() -> None:
    """Fail closed when a new project currency column has not been reviewed."""
    actual = {
        table.name: frozenset(column.name for column in table.c if "currency" in column.name)
        for table in Base.metadata.tables.values()
        if "project_id" in table.c and any("currency" in column.name for column in table.c)
    }
    if actual != {table: frozenset(columns) for table, columns in CURRENCY_COLUMNS.items()}:
        raise ConflictError(
            "Project currency correction is unavailable until all currency-bearing records "
            "are reviewed."
        )


def relabel_project_rows(
    session: Session,
    *,
    project_id: uuid.UUID,
    old_currency_id: uuid.UUID,
    new_currency_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    reason: str,
) -> dict[str, int]:
    """Relabel rows once; the caller owns the project lock and transaction."""
    require_complete_currency_map()
    counts: dict[str, int] = {}
    for table_name, columns in CURRENCY_COLUMNS.items():
        table = Base.metadata.tables[table_name]
        identity_column = "id" if "id" in table.c else "project_id"
        extras = []
        if "updated_at" in table.c:
            extras.append("updated_at = now()")
        if table_name == "ue_current_cost_settings":
            extras.append("revision = revision + 1")
        for column in columns:
            assignments = [f"{column} = :new_currency_id", *extras]
            ids = (
                session.execute(
                    text(
                        f"UPDATE {table_name} SET {', '.join(assignments)} "
                        f"WHERE project_id = :project_id AND {column} = :old_currency_id "
                        f"RETURNING {identity_column}"
                    ),
                    {
                        "project_id": project_id,
                        "old_currency_id": old_currency_id,
                        "new_currency_id": new_currency_id,
                    },
                )
                .scalars()
                .all()
            )
            for row_id in ids:
                record_event(
                    session,
                    action="project_currency.corrected_row",
                    entity_type=table_name,
                    entity_id=row_id,
                    actor_user_id=actor_user_id,
                    correlation_id=correlation_id,
                    reason=reason,
                    before={"project_id": project_id, column: old_currency_id},
                    after={"project_id": project_id, column: new_currency_id},
                )
            if ids:
                counts[f"{table_name}.{column}"] = len(ids)
    return counts
