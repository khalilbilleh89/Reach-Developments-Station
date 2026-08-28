"""Country configuration logic.

Stores configuration; calculates nothing. Every mutation writes its audit event
inside the same transaction and commits once.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.audit.service import record_event
from app.modules.settings.models import (
    CountryApprovalThreshold,
    CountryPack,
    Currency,
    ReferenceValue,
    TaxRule,
)

ENTITY_CURRENCY = "currency"
ENTITY_COUNTRY_PACK = "country_pack"
ENTITY_TAX_RULE = "tax_rule"
ENTITY_REFERENCE_VALUE = "reference_value"
ENTITY_APPROVAL_THRESHOLD = "country_approval_threshold"

#: Columns replaced wholesale by a threshold write. Listed once so the write
#: path, the snapshot and the response cannot drift apart.
THRESHOLD_FIELDS = (
    "discount_review_rate_fraction",
    "discount_review_amount",
    "pricing_requires_finance_approval",
    "pricing_requires_commercial_approval",
    "minimum_margin_rate_fraction",
    "custom_plan_min_down_payment_rate_fraction",
    "custom_plan_max_duration_months",
    "custom_plan_max_post_handover_rate_fraction",
    "custom_plan_max_npv_cost_rate_fraction",
    "receipt_reversal_requires_dual_control",
    "refund_requires_dual_control",
    "construction_variation_review_amount",
    "forecast_reset_variance_rate_fraction",
)


def _snapshot(instance: object, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: getattr(instance, field) for field in fields}


def _resolve_updates(
    changes: dict[str, object], *, fields: tuple[str, ...], clearable: frozenset[str]
) -> dict[str, object]:
    """Turn a PATCH body into the assignments to apply.

    The routes build ``changes`` with ``exclude_unset``, so an absent key and an
    explicit ``null`` arrive differently and must stay different: absent says
    nothing about the field, ``null`` says the value is gone. A ``null`` aimed at
    a column that cannot hold one is a client error, not something to drop on the
    floor and answer 200 to.
    """
    resolved: dict[str, object] = {}
    for field in fields:
        if field not in changes:
            continue
        value = changes[field]
        if value is None and field not in clearable:
            raise ValidationError(f"{field} cannot be null.")
        resolved[field] = value.strip() if isinstance(value, str) else value
    return resolved


# --------------------------------------------------------------------------- #
# Currencies
# --------------------------------------------------------------------------- #

_CURRENCY_FIELDS = ("id", "code", "name", "symbol", "minor_units", "is_active")
#: A currency code is immutable: rows elsewhere are read through it.
_CURRENCY_UPDATABLE = ("name", "symbol", "minor_units", "is_active")
_CURRENCY_CLEARABLE = frozenset({"symbol"})


def list_currencies(session: Session, *, is_active: bool | None = None) -> list[Currency]:
    statement = select(Currency).order_by(Currency.code)
    if is_active is not None:
        statement = statement.where(Currency.is_active.is_(is_active))
    return list(session.scalars(statement))


def get_currency(session: Session, currency_id: uuid.UUID) -> Currency:
    currency = session.get(Currency, currency_id)
    if currency is None:
        raise NotFoundError("Currency not found.")
    return currency


def create_currency(
    session: Session,
    *,
    code: str,
    name: str,
    symbol: str | None,
    minor_units: int,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> Currency:
    normalized = code.strip().upper()
    if not normalized.isalpha() or len(normalized) != 3:
        raise ValidationError("Currency code must be three letters.")
    if session.scalars(select(Currency).where(Currency.code == normalized)).first() is not None:
        raise ConflictError("A currency with this code already exists.")

    currency = Currency(
        code=normalized, name=name.strip(), symbol=symbol, minor_units=minor_units, is_active=True
    )
    session.add(currency)
    session.flush()
    record_event(
        session,
        action="currency.created",
        entity_type=ENTITY_CURRENCY,
        entity_id=currency.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        after=_snapshot(currency, _CURRENCY_FIELDS),
    )
    session.commit()
    session.refresh(currency)
    return currency


def _guard_currency_still_needed(session: Session, currency_id: uuid.UUID) -> None:
    """Refuse to retire a currency an active country pack still defaults to.

    A pack may not be *created* against an inactive currency, so letting one be
    deactivated underneath a live pack would leave that pack in a state the API
    would never have accepted. Packs that are themselves retired do not object:
    their currency is history too.
    """
    depended_on = session.scalars(
        select(CountryPack).where(
            CountryPack.default_currency_id == currency_id,
            CountryPack.is_active.is_(True),
        )
    ).first()
    if depended_on is not None:
        raise ConflictError(
            "Currency cannot be deactivated while it is the default currency "
            "of an active country pack."
        )


def update_currency(
    session: Session,
    *,
    currency_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **changes: object,
) -> Currency:
    currency = get_currency(session, currency_id)
    updates = _resolve_updates(changes, fields=_CURRENCY_UPDATABLE, clearable=_CURRENCY_CLEARABLE)
    if updates.get("is_active") is False:
        _guard_currency_still_needed(session, currency.id)
    before = _snapshot(currency, _CURRENCY_FIELDS)
    for field, value in updates.items():
        setattr(currency, field, value)
    session.flush()
    record_event(
        session,
        action="currency.updated",
        entity_type=ENTITY_CURRENCY,
        entity_id=currency.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(currency, _CURRENCY_FIELDS),
    )
    session.commit()
    session.refresh(currency)
    return currency


# --------------------------------------------------------------------------- #
# Country packs
# --------------------------------------------------------------------------- #

_PACK_FIELDS = (
    "id",
    "country_code",
    "name",
    "locale",
    "timezone",
    "default_currency_id",
    "area_unit",
    "fiscal_year_start_month",
    "is_active",
)


#: The country code is immutable: it is how a pack is identified elsewhere.
#: Nothing here is nullable, so no field is clearable.
_PACK_UPDATABLE = (
    "name",
    "locale",
    "timezone",
    "default_currency_id",
    "area_unit",
    "fiscal_year_start_month",
    "is_active",
)


def list_country_packs(session: Session, *, is_active: bool | None = None) -> list[CountryPack]:
    statement = select(CountryPack).order_by(CountryPack.name)
    if is_active is not None:
        statement = statement.where(CountryPack.is_active.is_(is_active))
    return list(session.scalars(statement))


def get_country_pack(session: Session, country_pack_id: uuid.UUID) -> CountryPack:
    pack = session.get(CountryPack, country_pack_id)
    if pack is None:
        raise NotFoundError("Country pack not found.")
    return pack


def _require_active_currency(session: Session, currency_id: uuid.UUID) -> Currency:
    currency = session.get(Currency, currency_id)
    if currency is None:
        raise ValidationError("Default currency does not exist.")
    if not currency.is_active:
        raise ValidationError("Default currency must be active.")
    return currency


def create_country_pack(
    session: Session,
    *,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    country_code: str,
    name: str,
    locale: str,
    timezone: str,
    default_currency_id: uuid.UUID,
    area_unit: str,
    fiscal_year_start_month: int,
) -> CountryPack:
    normalized = country_code.strip().upper()
    if not normalized.isalpha() or len(normalized) != 2:
        raise ValidationError("Country code must be two letters.")
    if (
        session.scalars(select(CountryPack).where(CountryPack.country_code == normalized)).first()
        is not None
    ):
        raise ConflictError("A country pack with this code already exists.")
    _require_active_currency(session, default_currency_id)

    pack = CountryPack(
        country_code=normalized,
        name=name.strip(),
        locale=locale.strip(),
        timezone=timezone.strip(),
        default_currency_id=default_currency_id,
        area_unit=area_unit,
        fiscal_year_start_month=fiscal_year_start_month,
        is_active=True,
    )
    session.add(pack)
    session.flush()
    record_event(
        session,
        action="country_pack.created",
        entity_type=ENTITY_COUNTRY_PACK,
        entity_id=pack.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        after=_snapshot(pack, _PACK_FIELDS),
    )
    session.commit()
    session.refresh(pack)
    return pack


def update_country_pack(
    session: Session,
    *,
    country_pack_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **changes: object,
) -> CountryPack:
    pack = get_country_pack(session, country_pack_id)
    updates = _resolve_updates(changes, fields=_PACK_UPDATABLE, clearable=frozenset())
    # Validate the state the pack will end up in, not only the fields the request
    # happens to name. Reactivating a retired pack revives its stored currency
    # reference too, and that currency may have been retired in the meantime —
    # checking only `default_currency_id` when present would let a live pack end
    # up pointing at a dead currency, which is the state pack creation and the
    # currency guard both exist to prevent.
    resulting_is_active = updates.get("is_active", pack.is_active)
    resulting_currency_id = updates.get("default_currency_id", pack.default_currency_id)
    if resulting_is_active:
        _require_active_currency(session, resulting_currency_id)
    before = _snapshot(pack, _PACK_FIELDS)
    for field, value in updates.items():
        setattr(pack, field, value)
    session.flush()
    record_event(
        session,
        action="country_pack.updated",
        entity_type=ENTITY_COUNTRY_PACK,
        entity_id=pack.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(pack, _PACK_FIELDS),
    )
    session.commit()
    session.refresh(pack)
    return pack


# --------------------------------------------------------------------------- #
# Tax rules
# --------------------------------------------------------------------------- #

_TAX_FIELDS = (
    "id",
    "country_pack_id",
    "tax_code",
    "label",
    "applies_to",
    "calculation_basis",
    "rate_fraction",
    "valid_from",
    "valid_to",
    "is_active",
)


#: ``valid_from`` is NOT NULL; only the end of the window may be cleared.
_TAX_UPDATABLE = (
    "label",
    "applies_to",
    "calculation_basis",
    "rate_fraction",
    "valid_from",
    "valid_to",
    "is_active",
)
_TAX_CLEARABLE = frozenset({"valid_to"})


def _ranges_overlap(a_from: date, a_to: date | None, b_from: date, b_to: date | None) -> bool:
    """Whether two half-bounded date ranges intersect. ``None`` means open-ended."""
    starts_before_other_ends = a_to is None or b_from <= a_to
    other_starts_before_this_ends = b_to is None or a_from <= b_to
    return starts_before_other_ends and other_starts_before_this_ends


def _guard_tax_overlap(
    session: Session,
    *,
    country_pack_id: uuid.UUID,
    tax_code: str,
    valid_from: date,
    valid_to: date | None,
    exclude_id: uuid.UUID | None,
) -> None:
    """Refuse a second active rule covering the same code and period.

    Superseding a rate means closing the old row's validity, not silently
    stacking a second active one: tax history has to stay readable.

    Locks the owning country pack first. Overlap is decided by reading what
    already exists and then writing, so without a lock two transactions can each
    read a clear period and each insert into it: both commit, the invariant is
    broken, and neither writer sees an error. Taking the row lock *before* the
    read serialises writers per country pack, which is the smallest unit that
    covers the invariant — the check never looks beyond one pack. The caller
    validates, mutates and commits inside this same transaction, so the lock is
    held for the whole decision and released by that commit.
    """
    if valid_to is not None and valid_to < valid_from:
        raise ValidationError("valid_to must not be earlier than valid_from.")

    owner = session.scalars(
        select(CountryPack).where(CountryPack.id == country_pack_id).with_for_update()
    ).first()
    if owner is None:
        raise NotFoundError("Country pack not found.")

    existing = session.scalars(
        select(TaxRule).where(
            TaxRule.country_pack_id == country_pack_id,
            TaxRule.tax_code == tax_code,
            TaxRule.is_active.is_(True),
        )
    )
    for rule in existing:
        if exclude_id is not None and rule.id == exclude_id:
            continue
        if _ranges_overlap(valid_from, valid_to, rule.valid_from, rule.valid_to):
            raise ConflictError(
                "An active tax rule for this code already covers part of that period."
            )


def list_tax_rules(session: Session, *, country_pack_id: uuid.UUID) -> list[TaxRule]:
    return list(
        session.scalars(
            select(TaxRule)
            .where(TaxRule.country_pack_id == country_pack_id)
            .order_by(TaxRule.tax_code, TaxRule.valid_from.desc())
        )
    )


def get_tax_rule(session: Session, tax_rule_id: uuid.UUID) -> TaxRule:
    rule = session.get(TaxRule, tax_rule_id)
    if rule is None:
        raise NotFoundError("Tax rule not found.")
    return rule


def create_tax_rule(
    session: Session,
    *,
    country_pack_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    tax_code: str,
    label: str,
    applies_to: str,
    calculation_basis: str,
    rate_fraction: Decimal,
    valid_from: date,
    valid_to: date | None,
) -> TaxRule:
    get_country_pack(session, country_pack_id)
    normalized_code = tax_code.strip().upper()
    _guard_tax_overlap(
        session,
        country_pack_id=country_pack_id,
        tax_code=normalized_code,
        valid_from=valid_from,
        valid_to=valid_to,
        exclude_id=None,
    )

    rule = TaxRule(
        country_pack_id=country_pack_id,
        tax_code=normalized_code,
        label=label.strip(),
        applies_to=applies_to,
        calculation_basis=calculation_basis,
        rate_fraction=rate_fraction,
        valid_from=valid_from,
        valid_to=valid_to,
        is_active=True,
    )
    session.add(rule)
    session.flush()
    record_event(
        session,
        action="tax_rule.created",
        entity_type=ENTITY_TAX_RULE,
        entity_id=rule.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        after=_snapshot(rule, _TAX_FIELDS),
    )
    session.commit()
    session.refresh(rule)
    return rule


def update_tax_rule(
    session: Session,
    *,
    tax_rule_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    reason: str | None = None,
    **changes: object,
) -> TaxRule:
    """Tax rules are never physically deleted; history stays visible."""
    rule = get_tax_rule(session, tax_rule_id)
    before = _snapshot(rule, _TAX_FIELDS)

    updates = _resolve_updates(changes, fields=_TAX_UPDATABLE, clearable=_TAX_CLEARABLE)
    # Validate the values the row will actually hold, not the ones it holds now:
    # clearing an end date reopens the rule and can collide with its successor.
    valid_from = updates.get("valid_from", rule.valid_from)
    valid_to = updates.get("valid_to", rule.valid_to)
    will_be_active = updates.get("is_active", rule.is_active)
    if will_be_active:
        _guard_tax_overlap(
            session,
            country_pack_id=rule.country_pack_id,
            tax_code=rule.tax_code,
            valid_from=valid_from,
            valid_to=valid_to,
            exclude_id=rule.id,
        )
    elif valid_to is not None and valid_to < valid_from:
        raise ValidationError("valid_to must not be earlier than valid_from.")

    for field, value in updates.items():
        setattr(rule, field, value)
    session.flush()
    record_event(
        session,
        action="tax_rule.updated",
        entity_type=ENTITY_TAX_RULE,
        entity_id=rule.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        reason=reason,
        before=before,
        after=_snapshot(rule, _TAX_FIELDS),
    )
    session.commit()
    session.refresh(rule)
    return rule


# --------------------------------------------------------------------------- #
# Reference values
# --------------------------------------------------------------------------- #

_REFERENCE_FIELDS = (
    "id",
    "country_pack_id",
    "category",
    "code",
    "label",
    "description",
    "sort_order",
    "is_active",
    "valid_from",
    "valid_to",
)


#: Both ends of the validity window are optional here, unlike a tax rule.
_REFERENCE_UPDATABLE = (
    "label",
    "description",
    "sort_order",
    "is_active",
    "valid_from",
    "valid_to",
)
_REFERENCE_CLEARABLE = frozenset({"description", "valid_from", "valid_to"})


def list_reference_values(
    session: Session,
    *,
    country_pack_id: uuid.UUID | None = None,
    category: str | None = None,
    include_inactive: bool = True,
) -> list[ReferenceValue]:
    """Inactive values remain listable: historical records still reference them."""
    statement = select(ReferenceValue).order_by(
        ReferenceValue.category, ReferenceValue.sort_order, ReferenceValue.code
    )
    if country_pack_id is not None:
        statement = statement.where(ReferenceValue.country_pack_id == country_pack_id)
    if category is not None:
        statement = statement.where(ReferenceValue.category == category.strip())
    if not include_inactive:
        statement = statement.where(ReferenceValue.is_active.is_(True))
    return list(session.scalars(statement))


def get_reference_value(session: Session, reference_value_id: uuid.UUID) -> ReferenceValue:
    value = session.get(ReferenceValue, reference_value_id)
    if value is None:
        raise NotFoundError("Reference value not found.")
    return value


def create_reference_value(
    session: Session,
    *,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    country_pack_id: uuid.UUID | None,
    category: str,
    code: str,
    label: str,
    description: str | None,
    sort_order: int,
    valid_from: date | None,
    valid_to: date | None,
) -> ReferenceValue:
    if country_pack_id is not None:
        get_country_pack(session, country_pack_id)
    if valid_from and valid_to and valid_to < valid_from:
        raise ValidationError("valid_to must not be earlier than valid_from.")

    normalized_category = category.strip()
    normalized_code = code.strip()
    duplicate = session.scalars(
        select(ReferenceValue).where(
            ReferenceValue.country_pack_id.is_(country_pack_id)
            if country_pack_id is None
            else ReferenceValue.country_pack_id == country_pack_id,
            ReferenceValue.category == normalized_category,
            ReferenceValue.code == normalized_code,
        )
    ).first()
    if duplicate is not None:
        raise ConflictError("A reference value with this scope, category and code already exists.")

    value = ReferenceValue(
        country_pack_id=country_pack_id,
        category=normalized_category,
        code=normalized_code,
        label=label.strip(),
        description=description,
        sort_order=sort_order,
        is_active=True,
        valid_from=valid_from,
        valid_to=valid_to,
    )
    session.add(value)
    session.flush()
    record_event(
        session,
        action="reference_value.created",
        entity_type=ENTITY_REFERENCE_VALUE,
        entity_id=value.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        after=_snapshot(value, _REFERENCE_FIELDS),
    )
    session.commit()
    session.refresh(value)
    return value


def update_reference_value(
    session: Session,
    *,
    reference_value_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **changes: object,
) -> ReferenceValue:
    value = get_reference_value(session, reference_value_id)
    before = _snapshot(value, _REFERENCE_FIELDS)

    updates = _resolve_updates(changes, fields=_REFERENCE_UPDATABLE, clearable=_REFERENCE_CLEARABLE)
    valid_from = updates.get("valid_from", value.valid_from)
    valid_to = updates.get("valid_to", value.valid_to)
    if valid_from and valid_to and valid_to < valid_from:
        raise ValidationError("valid_to must not be earlier than valid_from.")

    for field, item in updates.items():
        setattr(value, field, item)
    session.flush()
    record_event(
        session,
        action="reference_value.updated",
        entity_type=ENTITY_REFERENCE_VALUE,
        entity_id=value.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        before=before,
        after=_snapshot(value, _REFERENCE_FIELDS),
    )
    session.commit()
    session.refresh(value)
    return value


# --------------------------------------------------------------------------- #
# Approval thresholds
# --------------------------------------------------------------------------- #


def get_approval_thresholds(
    session: Session, *, country_pack_id: uuid.UUID
) -> CountryApprovalThreshold:
    get_country_pack(session, country_pack_id)
    thresholds = session.scalars(
        select(CountryApprovalThreshold).where(
            CountryApprovalThreshold.country_pack_id == country_pack_id
        )
    ).first()
    if thresholds is None:
        raise NotFoundError("Approval thresholds have not been configured for this country pack.")
    return thresholds


def write_approval_thresholds(
    session: Session,
    *,
    country_pack_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
    reason: str | None,
    values: dict[str, Any],
) -> CountryApprovalThreshold:
    """Create or fully replace one country pack's control limits."""
    get_country_pack(session, country_pack_id)
    thresholds = session.scalars(
        select(CountryApprovalThreshold).where(
            CountryApprovalThreshold.country_pack_id == country_pack_id
        )
    ).first()

    created = thresholds is None
    before = None if created else _snapshot(thresholds, THRESHOLD_FIELDS)
    if thresholds is None:
        thresholds = CountryApprovalThreshold(country_pack_id=country_pack_id)
        session.add(thresholds)

    for field in THRESHOLD_FIELDS:
        setattr(thresholds, field, values.get(field))
    session.flush()

    record_event(
        session,
        action="approval_threshold.created" if created else "approval_threshold.updated",
        entity_type=ENTITY_APPROVAL_THRESHOLD,
        entity_id=thresholds.id,
        correlation_id=correlation_id,
        actor_user_id=actor_user_id,
        reason=reason,
        before=before,
        after=_snapshot(thresholds, THRESHOLD_FIELDS),
    )
    session.commit()
    session.refresh(thresholds)
    return thresholds
