"""Set-based cost control reads, keeping ex-tax commitments separate from cash."""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.standing import as_of_bound
from app.modules.construction import calculator
from app.modules.construction import models as m


@dataclass
class ConstructionPosition:
    budget_id: uuid.UUID | None = None
    budget_currency: uuid.UUID | None = None
    control_budget: Decimal | None = None
    forecast_id: uuid.UUID | None = None
    forecast_currency: uuid.UUID | None = None
    eac: Decimal | None = None
    revised_commitment: dict[uuid.UUID, Decimal] = field(default_factory=dict)
    paid: dict[uuid.UUID, Decimal] = field(default_factory=dict)
    eac_reason: str = "No active Construction forecast."


def positions(session: Session, project_ids: Select) -> dict[uuid.UUID, ConstructionPosition]:
    result: dict[uuid.UUID, ConstructionPosition] = {}
    for version, approved, contingency in session.execute(
        select(
            m.BudgetVersion,
            func.sum(m.BudgetLine.approved_budget_amount),
            func.sum(m.BudgetLine.contingency_amount),
        )
        .outerjoin(m.BudgetLine, m.BudgetLine.budget_version_id == m.BudgetVersion.id)
        .where(
            m.BudgetVersion.project_id.in_(project_ids), m.BudgetVersion.status == m.BUDGET_ACTIVE
        )
        .group_by(m.BudgetVersion.id)
    ):
        target = result.setdefault(version.project_id, ConstructionPosition())
        target.budget_id = version.id
        target.budget_currency = version.currency_id
        target.control_budget = calculator.control_budget(
            approved_budget=approved or Decimal(0), contingency=contingency or Decimal(0)
        )
    for pid, currency, original in session.execute(
        select(
            m.Contract.project_id,
            m.Contract.currency_id,
            func.sum(m.ContractLine.original_amount_ex_tax),
        )
        .join(m.ContractLine, m.ContractLine.contract_id == m.Contract.id)
        .where(m.Contract.project_id.in_(project_ids), m.Contract.status.in_(m.CONTRACT_COMMITTING))
        .group_by(m.Contract.project_id, m.Contract.currency_id)
    ):
        result.setdefault(pid, ConstructionPosition()).revised_commitment[currency] = (
            calculator.revised_commitment(
                original_amount=original, approved_variation_delta=Decimal(0)
            )
        )
    for pid, currency, delta in session.execute(
        select(
            m.Contract.project_id,
            m.Contract.currency_id,
            func.sum(m.VariationLine.value_delta_ex_tax),
        )
        .join(m.Variation, m.Variation.contract_id == m.Contract.id)
        .join(m.VariationLine, m.VariationLine.variation_id == m.Variation.id)
        .where(
            m.Contract.project_id.in_(project_ids),
            m.Contract.status.in_(m.CONTRACT_COMMITTING),
            m.Variation.status == m.VARIATION_APPROVED,
        )
        .group_by(m.Contract.project_id, m.Contract.currency_id)
    ):
        target = result.setdefault(pid, ConstructionPosition())
        target.revised_commitment[currency] = calculator.revised_commitment(
            original_amount=target.revised_commitment.get(currency, Decimal(0)),
            approved_variation_delta=delta,
        )
    forecasts = list(
        session.scalars(
            select(m.ForecastVersion).where(
                m.ForecastVersion.project_id.in_(project_ids),
                m.ForecastVersion.status == m.FORECAST_ACTIVE,
            )
        )
    )
    forecast_ids = [row.id for row in forecasts]
    remaining = dict(
        session.execute(
            select(
                m.ForecastLine.forecast_version_id,
                func.sum(m.ForecastLine.forecast_remaining_amount_ex_tax),
            )
            .where(m.ForecastLine.forecast_version_id.in_(forecast_ids))
            .group_by(m.ForecastLine.forecast_version_id)
        ).all()
    )
    # Historical certification uses the same exclusive UTC bound as the owner.
    certificates = list(
        session.execute(
            select(
                m.Certificate,
                m.Contract.currency_id,
                func.sum(m.CertificateLine.current_work_value_ex_tax),
            )
            .join(m.Contract, m.Contract.id == m.Certificate.contract_id)
            .join(m.CertificateLine, m.CertificateLine.certificate_id == m.Certificate.id)
            .where(m.Certificate.project_id.in_(project_ids))
            .group_by(m.Certificate.id, m.Contract.currency_id)
        )
    )
    by_project: dict[uuid.UUID, list] = {}
    for row in certificates:
        by_project.setdefault(row[0].project_id, []).append(row)
    for version in forecasts:
        target = result.setdefault(version.project_id, ConstructionPosition())
        target.forecast_id = version.id
        target.forecast_currency = version.currency_id
        bound = as_of_bound(version.as_of_date)
        standing = [
            (currency, value)
            for cert, currency, value in by_project.get(version.project_id, [])
            if cert.certified_at is not None
            and cert.certified_at < bound
            and (cert.reversed_at is None or cert.reversed_at >= bound)
        ]
        if any(currency != version.currency_id for currency, _ in standing):
            target.eac_reason = (
                "Construction forecast and certified sources use incompatible currencies."
            )
        else:
            target.eac = calculator.estimate_at_completion(
                certified_to_date=sum((value for _, value in standing), Decimal(0)),
                forecast_remaining=remaining.get(version.id, Decimal(0)),
            )
            target.eac_reason = ""
    for pid, currency, amount in session.execute(
        select(m.Payment.project_id, m.Payment.currency_id, func.sum(m.Payment.amount))
        .where(m.Payment.project_id.in_(project_ids), m.Payment.status == m.PAYMENT_CONFIRMED)
        .group_by(m.Payment.project_id, m.Payment.currency_id)
    ):
        result.setdefault(pid, ConstructionPosition()).paid[currency] = amount
    return result
