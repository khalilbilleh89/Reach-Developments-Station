"""Country configuration routes.

Reads are open to any authenticated user: every domain needs to resolve a
currency or a lookup label. Writes are System Administrator only.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.modules.access.dependencies import ActiveActor, DbSession, SystemAdmin
from app.modules.settings import service
from app.modules.settings.schemas import (
    ApprovalThresholdRead,
    ApprovalThresholdWriteRequest,
    CountryPackCreateRequest,
    CountryPackRead,
    CountryPackUpdateRequest,
    CurrencyCreateRequest,
    CurrencyRead,
    CurrencyUpdateRequest,
    ReferenceValueCreateRequest,
    ReferenceValueRead,
    ReferenceValueUpdateRequest,
    TaxRuleCreateRequest,
    TaxRuleRead,
    TaxRuleUpdateRequest,
)

router = APIRouter(prefix="/settings", tags=["settings"])


# --------------------------------------------------------------------------- #
# Currencies
# --------------------------------------------------------------------------- #


@router.get("/currencies", response_model=list[CurrencyRead], summary="List currencies")
def list_currencies(
    session: DbSession,
    _actor: ActiveActor,
    is_active: Annotated[bool | None, Query()] = None,
) -> list[CurrencyRead]:
    return [
        CurrencyRead.model_validate(currency)
        for currency in service.list_currencies(session, is_active=is_active)
    ]


@router.post(
    "/currencies",
    response_model=CurrencyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a currency",
)
def create_currency(
    payload: CurrencyCreateRequest,
    session: DbSession,
    actor: SystemAdmin,
) -> CurrencyRead:
    currency = service.create_currency(
        session,
        code=payload.code,
        name=payload.name,
        symbol=payload.symbol,
        minor_units=payload.minor_units,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
    )
    return CurrencyRead.model_validate(currency)


@router.patch("/currencies/{currency_id}", response_model=CurrencyRead, summary="Update a currency")
def update_currency(
    currency_id: uuid.UUID,
    payload: CurrencyUpdateRequest,
    session: DbSession,
    actor: SystemAdmin,
) -> CurrencyRead:
    currency = service.update_currency(
        session,
        currency_id=currency_id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **payload.model_dump(exclude_unset=True),
    )
    return CurrencyRead.model_validate(currency)


# --------------------------------------------------------------------------- #
# Country packs
# --------------------------------------------------------------------------- #


@router.get("/country-packs", response_model=list[CountryPackRead], summary="List country packs")
def list_country_packs(
    session: DbSession,
    _actor: ActiveActor,
    is_active: Annotated[bool | None, Query()] = None,
) -> list[CountryPackRead]:
    return [
        CountryPackRead.model_validate(pack)
        for pack in service.list_country_packs(session, is_active=is_active)
    ]


@router.post(
    "/country-packs",
    response_model=CountryPackRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a country pack",
)
def create_country_pack(
    payload: CountryPackCreateRequest,
    session: DbSession,
    actor: SystemAdmin,
) -> CountryPackRead:
    pack = service.create_country_pack(
        session,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        country_code=payload.country_code,
        name=payload.name,
        locale=payload.locale,
        timezone=payload.timezone,
        default_currency_id=payload.default_currency_id,
        area_unit=payload.area_unit,
        fiscal_year_start_month=payload.fiscal_year_start_month,
    )
    return CountryPackRead.model_validate(pack)


@router.get(
    "/country-packs/{country_pack_id}",
    response_model=CountryPackRead,
    summary="Read a country pack",
)
def read_country_pack(
    country_pack_id: uuid.UUID,
    session: DbSession,
    _actor: ActiveActor,
) -> CountryPackRead:
    return CountryPackRead.model_validate(service.get_country_pack(session, country_pack_id))


@router.patch(
    "/country-packs/{country_pack_id}",
    response_model=CountryPackRead,
    summary="Update a country pack",
)
def update_country_pack(
    country_pack_id: uuid.UUID,
    payload: CountryPackUpdateRequest,
    session: DbSession,
    actor: SystemAdmin,
) -> CountryPackRead:
    pack = service.update_country_pack(
        session,
        country_pack_id=country_pack_id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **payload.model_dump(exclude_unset=True),
    )
    return CountryPackRead.model_validate(pack)


# --------------------------------------------------------------------------- #
# Tax rules
# --------------------------------------------------------------------------- #


@router.get(
    "/country-packs/{country_pack_id}/tax-rules",
    response_model=list[TaxRuleRead],
    summary="List tax rules for a country pack",
)
def list_tax_rules(
    country_pack_id: uuid.UUID,
    session: DbSession,
    _actor: ActiveActor,
) -> list[TaxRuleRead]:
    return [
        TaxRuleRead.model_validate(rule)
        for rule in service.list_tax_rules(session, country_pack_id=country_pack_id)
    ]


@router.post(
    "/country-packs/{country_pack_id}/tax-rules",
    response_model=TaxRuleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tax rule",
)
def create_tax_rule(
    country_pack_id: uuid.UUID,
    payload: TaxRuleCreateRequest,
    session: DbSession,
    actor: SystemAdmin,
) -> TaxRuleRead:
    rule = service.create_tax_rule(
        session,
        country_pack_id=country_pack_id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        tax_code=payload.tax_code,
        label=payload.label,
        applies_to=payload.applies_to,
        calculation_basis=payload.calculation_basis,
        rate_fraction=payload.rate_fraction,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
    )
    return TaxRuleRead.model_validate(rule)


@router.patch("/tax-rules/{tax_rule_id}", response_model=TaxRuleRead, summary="Update a tax rule")
def update_tax_rule(
    tax_rule_id: uuid.UUID,
    payload: TaxRuleUpdateRequest,
    session: DbSession,
    actor: SystemAdmin,
) -> TaxRuleRead:
    changes = payload.model_dump(exclude_unset=True)
    reason = changes.pop("reason", None)
    rule = service.update_tax_rule(
        session,
        tax_rule_id=tax_rule_id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason,
        **changes,
    )
    return TaxRuleRead.model_validate(rule)


# --------------------------------------------------------------------------- #
# Reference values
# --------------------------------------------------------------------------- #


@router.get(
    "/reference-values", response_model=list[ReferenceValueRead], summary="List reference values"
)
def list_reference_values(
    session: DbSession,
    _actor: ActiveActor,
    country_pack_id: Annotated[uuid.UUID | None, Query()] = None,
    category: Annotated[str | None, Query(max_length=64)] = None,
    include_inactive: Annotated[bool, Query()] = True,
) -> list[ReferenceValueRead]:
    return [
        ReferenceValueRead.model_validate(value)
        for value in service.list_reference_values(
            session,
            country_pack_id=country_pack_id,
            category=category,
            include_inactive=include_inactive,
        )
    ]


@router.post(
    "/reference-values",
    response_model=ReferenceValueRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a reference value",
)
def create_reference_value(
    payload: ReferenceValueCreateRequest,
    session: DbSession,
    actor: SystemAdmin,
) -> ReferenceValueRead:
    value = service.create_reference_value(
        session,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        country_pack_id=payload.country_pack_id,
        category=payload.category,
        code=payload.code,
        label=payload.label,
        description=payload.description,
        sort_order=payload.sort_order,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
    )
    return ReferenceValueRead.model_validate(value)


@router.patch(
    "/reference-values/{reference_value_id}",
    response_model=ReferenceValueRead,
    summary="Update a reference value",
)
def update_reference_value(
    reference_value_id: uuid.UUID,
    payload: ReferenceValueUpdateRequest,
    session: DbSession,
    actor: SystemAdmin,
) -> ReferenceValueRead:
    value = service.update_reference_value(
        session,
        reference_value_id=reference_value_id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **payload.model_dump(exclude_unset=True),
    )
    return ReferenceValueRead.model_validate(value)


# --------------------------------------------------------------------------- #
# Approval thresholds
# --------------------------------------------------------------------------- #


@router.get(
    "/country-packs/{country_pack_id}/approval-thresholds",
    response_model=ApprovalThresholdRead,
    summary="Read country approval thresholds",
)
def read_approval_thresholds(
    country_pack_id: uuid.UUID,
    session: DbSession,
    _actor: ActiveActor,
) -> ApprovalThresholdRead:
    return ApprovalThresholdRead.model_validate(
        service.get_approval_thresholds(session, country_pack_id=country_pack_id)
    )


@router.put(
    "/country-packs/{country_pack_id}/approval-thresholds",
    response_model=ApprovalThresholdRead,
    summary="Replace country approval thresholds",
)
def write_approval_thresholds(
    country_pack_id: uuid.UUID,
    payload: ApprovalThresholdWriteRequest,
    session: DbSession,
    actor: SystemAdmin,
) -> ApprovalThresholdRead:
    values = payload.model_dump()
    reason = values.pop("reason", None)
    thresholds = service.write_approval_thresholds(
        session,
        country_pack_id=country_pack_id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason,
        values=values,
    )
    return ApprovalThresholdRead.model_validate(thresholds)
