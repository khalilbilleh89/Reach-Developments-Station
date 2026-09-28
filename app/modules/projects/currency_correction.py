"""Atomic orchestration for correcting a project's mistaken base denomination.

Projects owns the command and the project lock. Each sibling domain owns its
eligible persistence changes through a narrow, caller-transaction contract.
Explicit pricing choices and append-only legal fee evidence remain untouched.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.base import Base
from app.modules.audit.service import record_event
from app.modules.cashflow import currency_correction as cashflow_correction
from app.modules.collections import currency_correction as collections_correction
from app.modules.commissions import currency_correction as commissions_correction
from app.modules.construction import currency_correction as construction_correction
from app.modules.payment_plans import currency_correction as payment_plans_correction
from app.modules.pricing import currency_correction as pricing_correction
from app.modules.projects.models import Project
from app.modules.sales import currency_correction as sales_correction
from app.modules.settings.models import Currency
from app.modules.unit_economics import currency_correction as unit_economics_correction


@dataclass(frozen=True)
class CurrencyFieldPolicy:
    owner: str
    semantics: str
    correction: str


# This is a review boundary, not a mutation map. Every project-scoped currency
# column is listed, including the fields that correction deliberately preserves.
FIELD_POLICIES: dict[str, dict[str, CurrencyFieldPolicy]] = {
    "cashflow_development_movements": {
        "currency_id": CurrencyFieldPolicy("Cashflow", "project-base-only cash movement", "relabel")
    },
    "cashflow_financing_movements": {
        "currency_id": CurrencyFieldPolicy("Cashflow", "project-base-only cash movement", "relabel")
    },
    "cashflow_forecast_versions": {
        "currency_id": CurrencyFieldPolicy("Cashflow", "project-base inherited forecast", "relabel")
    },
    "collection_receipts": {
        "currency_id": CurrencyFieldPolicy(
            "Collections", "sale-inherited cash denomination", "sale_chain"
        )
    },
    "collection_refunds": {
        "currency_id": CurrencyFieldPolicy(
            "Collections", "sale-inherited cash denomination", "sale_chain"
        )
    },
    "commission_grants": {
        "currency_id": CurrencyFieldPolicy(
            "Commissions", "sale-inherited frozen snapshot", "sale_chain"
        )
    },
    "construction_budget_versions": {
        "currency_id": CurrencyFieldPolicy(
            "Construction", "project-base inherited budget", "relabel"
        )
    },
    "construction_contracts": {
        "currency_id": CurrencyFieldPolicy("Construction", "project-base-only contract", "relabel")
    },
    "construction_forecast_versions": {
        "currency_id": CurrencyFieldPolicy(
            "Construction", "project-base inherited forecast", "relabel"
        )
    },
    "construction_payments": {
        "currency_id": CurrencyFieldPolicy("Construction", "contract-inherited payment", "relabel")
    },
    "market_benchmarks": {
        "currency_id": CurrencyFieldPolicy("Pricing", "explicit external observation", "preserve")
    },
    "marketing_rental_scenarios": {
        "currency_id": CurrencyFieldPolicy(
            "Marketing", "explicit sourced rental assumption", "preserve"
        )
    },
    "payment_plan_versions": {
        "currency_id": CurrencyFieldPolicy(
            "Payment Plans", "sale-inherited frozen schedule", "sale_chain"
        )
    },
    "pricing_configurations": {
        "pricing_currency_id": CurrencyFieldPolicy("Pricing", "explicit pricing policy", "preserve")
    },
    "projects": {
        "base_currency_id": CurrencyFieldPolicy(
            "Projects", "governing project denomination", "replace"
        ),
        "reporting_currency_id": CurrencyFieldPolicy(
            "Projects", "explicit or old-base-following reporting choice", "follow_if_old_base"
        ),
    },
    "reservations": {
        "currency_id": CurrencyFieldPolicy(
            "Sales", "price-inherited frozen quote", "direct_price_chain"
        ),
        "deposit_currency_id": CurrencyFieldPolicy(
            "Sales", "reservation-inherited deposit evidence", "direct_price_chain"
        ),
    },
    "sale_contract_tax_lines": {
        "currency_id": CurrencyFieldPolicy("Sales", "sale-inherited frozen tax", "sale_chain")
    },
    "sale_contracts": {
        "currency_id": CurrencyFieldPolicy(
            "Sales", "reservation-inherited frozen contract", "sale_chain"
        )
    },
    "sale_legal_events": {
        "currency_id": CurrencyFieldPolicy(
            "Sales", "explicit append-only legal fee evidence", "preserve"
        )
    },
    "ue_current_cost_settings": {
        "currency_id": CurrencyFieldPolicy("Unit Economics", "project-base live inputs", "relabel")
    },
    "unit_economics_allocation_versions": {
        "currency_id": CurrencyFieldPolicy(
            "Unit Economics", "project-base inherited allocation", "relabel"
        )
    },
    "unit_economics_unit_costs": {
        "currency_id": CurrencyFieldPolicy(
            "Unit Economics", "project-base inherited unit cost", "relabel"
        )
    },
    "unit_price_versions": {
        "currency_id": CurrencyFieldPolicy(
            "Pricing", "direct project-base or configured pricing snapshot", "direct_only"
        )
    },
}


def require_complete_currency_review() -> None:
    """Fail closed when a new project currency field lacks an ownership decision."""
    actual = {
        table.name: frozenset(column.name for column in table.c if "currency" in column.name)
        for table in Base.metadata.tables.values()
        if ("project_id" in table.c or table.name == "projects")
        and any("currency" in column.name for column in table.c)
    }
    reviewed = {table: frozenset(columns) for table, columns in FIELD_POLICIES.items()}
    if actual != reviewed:
        raise ConflictError(
            "Project currency correction is unavailable until every currency-bearing "
            "project record has a reviewed ownership policy."
        )


def correct_project_base_currency(
    session: Session,
    *,
    project_id: uuid.UUID,
    expected_base_currency_id: uuid.UUID,
    target_currency_id: uuid.UUID,
    keep_amounts_unchanged: bool,
    reason: str,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> Project:
    """Correct one denomination label atomically without changing numeric values."""
    if not keep_amounts_unchanged:
        raise ValidationError("Acknowledge that every numeric amount will remain unchanged.")
    clean_reason = reason.strip()
    if len(clean_reason) < 8:
        raise ValidationError("Explain the currency correction in at least eight characters.")

    project = session.scalar(
        select(Project)
        .where(Project.id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if project is None:
        raise NotFoundError("Project not found.")
    if project.base_currency_id != expected_base_currency_id:
        raise ConflictError("The project base currency changed. Refresh before correcting it.")
    if target_currency_id == project.base_currency_id:
        raise ValidationError("Choose a different base currency.")
    target = session.get(Currency, target_currency_id)
    if target is None:
        raise ValidationError("Target currency does not exist.")
    if not target.is_active:
        raise ValidationError("Target currency must be active.")

    require_complete_currency_review()
    old_currency_id = project.base_currency_id
    old_reporting_currency_id = project.reporting_currency_id
    counts: dict[str, int] = {}
    try:
        pricing = pricing_correction.correct_project_base_currency(
            session,
            project_id=project.id,
            old_currency_id=old_currency_id,
            new_currency_id=target_currency_id,
        )
        counts.update(pricing.counts)
        sales = sales_correction.correct_project_base_currency(
            session,
            project_id=project.id,
            old_currency_id=old_currency_id,
            new_currency_id=target_currency_id,
            direct_price_version_ids=pricing.direct_price_version_ids,
        )
        counts.update(sales.counts)
        for correction in (
            cashflow_correction,
            construction_correction,
            unit_economics_correction,
        ):
            counts.update(
                correction.correct_project_base_currency(
                    session,
                    project_id=project.id,
                    old_currency_id=old_currency_id,
                    new_currency_id=target_currency_id,
                )
            )
        for correction in (
            payment_plans_correction,
            collections_correction,
            commissions_correction,
        ):
            counts.update(
                correction.correct_project_base_currency(
                    session,
                    project_id=project.id,
                    old_currency_id=old_currency_id,
                    new_currency_id=target_currency_id,
                    sale_contract_ids=sales.sale_contract_ids,
                )
            )

        project.base_currency_id = target_currency_id
        if project.reporting_currency_id == old_currency_id:
            project.reporting_currency_id = target_currency_id
        session.flush()
        record_event(
            session,
            action="project_currency.corrected",
            entity_type="project",
            entity_id=project.id,
            actor_user_id=actor_user_id,
            correlation_id=correlation_id,
            reason=clean_reason,
            before={
                "base_currency_id": old_currency_id,
                "reporting_currency_id": old_reporting_currency_id,
            },
            after={
                "base_currency_id": target_currency_id,
                "reporting_currency_id": project.reporting_currency_id,
                "amounts_unchanged": True,
                "corrected_rows": dict(sorted(counts.items())),
                "preserved_explicit_fields": [
                    "pricing_configurations.pricing_currency_id",
                    "market_benchmarks.currency_id",
                    "marketing_rental_scenarios.currency_id",
                    "sale_legal_events.currency_id",
                ],
            },
        )
        session.commit()
        session.refresh(project)
        return project
    except Exception:
        session.rollback()
        raise
