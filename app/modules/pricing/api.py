"""Pricing routes: configuration, rules, escalation, benchmarks, prices, quotes.

Handlers validate, authorise and orchestrate. Every rule about what a price may
be lives in the service; every rule about who may reach it lives in
``permissions.py``. A route that decided either for itself would be the one that
later disagrees with the rest.

Status is never a PATCH. Draft, submitted, approved, active and superseded are
reached through named routes because each is a different act with a different
right attached, and a status column a client can set is an approval a client can
grant itself.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.core.errors import NotFoundError, ValidationError
from app.modules.access.dependencies import ActiveActor, ActorContext, DbSession
from app.modules.inventory.models import Building, Floor, Unit
from app.modules.pricing import service
from app.modules.pricing.models import (
    STATUS_ACTIVE,
    STATUS_SUPERSEDED,
    PricingConfiguration,
    UnitPriceVersion,
)
from app.modules.pricing.permissions import (
    PricingProject,
    require_internal_price_reader,
    require_operational_project,
    require_priceable_unit,
    require_pricing_approver,
    require_pricing_writer,
    require_quote_reader,
    sees_internal_prices,
    visible_unit_ids,
    visible_units_for_pricing,
)
from app.modules.pricing.schemas import (
    AreaRuleCreateRequest,
    AreaRuleRead,
    AreaRuleUpdateRequest,
    BenchmarkCreateRequest,
    BenchmarkRead,
    BenchmarkUpdateRequest,
    BulkGenerateRequest,
    BulkVersionRequest,
    EscalationActivateRequest,
    EscalationActivationRead,
    EscalationRuleCreateRequest,
    EscalationRuleRead,
    EscalationRuleUpdateRequest,
    OptionalReasonRequest,
    PremiumRuleCreateRequest,
    PremiumRuleRead,
    PremiumRuleUpdateRequest,
    PriceComponentRead,
    PriceRegister,
    PriceRegisterRow,
    PriceVersionCreateRequest,
    PriceVersionDetail,
    PriceVersionRead,
    PriceVersionUpdateRequest,
    PricingConfigurationCreateRequest,
    PricingConfigurationRead,
    PricingConfigurationUpdateRequest,
    PricingOverview,
    QuotePreviewRead,
    QuotePreviewRequest,
    ReasonRequest,
    UnitPricingRead,
)
from app.modules.projects.models import Project

router = APIRouter(prefix="/projects", tags=["pricing"])

#: A page of the price register. Large enough for a floor of units, bounded so
#: one request cannot ask for a whole development's pricing at once.
_MAX_PAGE = 200

_VERSION_NOT_FOUND = "Price version not found."


def _detail(session: DbSession, version: UnitPriceVersion) -> PriceVersionDetail:
    components = service.list_components(session, version_id=version.id)
    return PriceVersionDetail(
        **PriceVersionRead.model_validate(version).model_dump(),
        components=[PriceComponentRead.model_validate(item) for item in components],
        basis_snapshot_json=version.basis_snapshot_json,
    )


def _require_configuration(
    session: DbSession, project: Project, configuration_id: uuid.UUID
) -> PricingConfiguration:
    return service.get_configuration(
        session, project_id=project.id, configuration_id=configuration_id
    )


def _require_version(
    session: DbSession,
    project: Project,
    actor: ActorContext,
    version_id: uuid.UUID,
    *,
    internal: bool | None = None,
) -> UnitPriceVersion:
    """Load a price version the caller may see, or 404.

    Two separate reasons to refuse, both answering the same way. The unit may be
    in a phase the caller was not granted; or the version may be a draft and the
    caller a sales user, who has no business seeing a number nobody has agreed
    to. A 403 for either would confirm the identifier names something real.
    """
    version = service.get_price_version(session, project_id=project.id, version_id=version_id)
    try:
        require_priceable_unit(session, project=project, unit_id=version.unit_id, actor=actor)
    except NotFoundError as exc:
        raise NotFoundError(_VERSION_NOT_FOUND) from exc
    allowed_internal = sees_internal_prices(actor) if internal is None else internal
    if not allowed_internal and version.status not in (STATUS_ACTIVE, STATUS_SUPERSEDED):
        raise NotFoundError(_VERSION_NOT_FOUND)
    return version


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/pricing/configurations",
    response_model=list[PricingConfigurationRead],
    summary="List a project's pricing configurations",
)
def list_configurations(
    session: DbSession, actor: ActiveActor, project: PricingProject
) -> list[PricingConfigurationRead]:
    require_internal_price_reader(actor)
    return [
        PricingConfigurationRead.model_validate(item)
        for item in service.list_configurations(session, project_id=project.id)
    ]


@router.post(
    "/{project_id}/pricing/configurations",
    response_model=PricingConfigurationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Open a draft pricing configuration",
)
def create_configuration(
    payload: PricingConfigurationCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PricingConfigurationRead:
    require_pricing_writer(actor)
    require_operational_project(project)
    configuration = service.create_configuration(
        session, project=project, actor=actor, **payload.model_dump()
    )
    return PricingConfigurationRead.model_validate(configuration)


@router.get(
    "/{project_id}/pricing/configurations/{configuration_id}",
    response_model=PricingConfigurationRead,
    summary="Read a pricing configuration",
)
def read_configuration(
    configuration_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PricingConfigurationRead:
    require_internal_price_reader(actor)
    return PricingConfigurationRead.model_validate(
        _require_configuration(session, project, configuration_id)
    )


@router.patch(
    "/{project_id}/pricing/configurations/{configuration_id}",
    response_model=PricingConfigurationRead,
    summary="Change a draft pricing configuration",
)
def update_configuration(
    configuration_id: uuid.UUID,
    payload: PricingConfigurationUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PricingConfigurationRead:
    require_pricing_writer(actor)
    configuration = _require_configuration(session, project, configuration_id)
    updated = service.update_configuration(
        session,
        project=project,
        configuration=configuration,
        actor=actor,
        **payload.model_dump(exclude_unset=True),
    )
    return PricingConfigurationRead.model_validate(updated)


@router.post(
    "/{project_id}/pricing/configurations/{configuration_id}/submit",
    response_model=PricingConfigurationRead,
    summary="Submit a pricing configuration for approval",
)
def submit_configuration(
    configuration_id: uuid.UUID,
    payload: OptionalReasonRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PricingConfigurationRead:
    require_pricing_writer(actor)
    configuration = _require_configuration(session, project, configuration_id)
    return PricingConfigurationRead.model_validate(
        service.submit_configuration(
            session,
            project=project,
            configuration=configuration,
            actor=actor,
            change_reason=payload.reason,
        )
    )


@router.post(
    "/{project_id}/pricing/configurations/{configuration_id}/return",
    response_model=PricingConfigurationRead,
    summary="Return a submitted pricing configuration to its author",
)
def return_configuration(
    configuration_id: uuid.UUID,
    payload: ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PricingConfigurationRead:
    require_pricing_approver(actor)
    configuration = _require_configuration(session, project, configuration_id)
    return PricingConfigurationRead.model_validate(
        service.return_configuration(
            session,
            project=project,
            configuration=configuration,
            actor=actor,
            reason=payload.reason,
        )
    )


@router.post(
    "/{project_id}/pricing/configurations/{configuration_id}/approve",
    response_model=PricingConfigurationRead,
    summary="Approve a pricing configuration",
)
def approve_configuration(
    configuration_id: uuid.UUID,
    payload: ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PricingConfigurationRead:
    require_pricing_approver(actor)
    configuration = _require_configuration(session, project, configuration_id)
    return PricingConfigurationRead.model_validate(
        service.approve_configuration(
            session,
            project=project,
            configuration=configuration,
            actor=actor,
            reason=payload.reason,
        )
    )


@router.post(
    "/{project_id}/pricing/configurations/{configuration_id}/activate",
    response_model=PricingConfigurationRead,
    summary="Activate an approved pricing configuration",
)
def activate_configuration(
    configuration_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PricingConfigurationRead:
    require_pricing_approver(actor)
    configuration = _require_configuration(session, project, configuration_id)
    return PricingConfigurationRead.model_validate(
        service.activate_configuration(
            session, project=project, configuration=configuration, actor=actor
        )
    )


# --------------------------------------------------------------------------- #
# Area and premium rules
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/pricing/configurations/{configuration_id}/area-rules",
    response_model=list[AreaRuleRead],
    summary="List the area pricing rules of a configuration",
)
def list_area_rules(
    configuration_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> list[AreaRuleRead]:
    require_internal_price_reader(actor)
    configuration = _require_configuration(session, project, configuration_id)
    return [
        AreaRuleRead.model_validate(rule)
        for rule in service.list_area_rules(session, configuration_id=configuration.id)
    ]


@router.post(
    "/{project_id}/pricing/configurations/{configuration_id}/area-rules",
    response_model=AreaRuleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Price an area type",
)
def create_area_rule(
    configuration_id: uuid.UUID,
    payload: AreaRuleCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> AreaRuleRead:
    require_pricing_writer(actor)
    configuration = _require_configuration(session, project, configuration_id)
    return AreaRuleRead.model_validate(
        service.create_area_rule(
            session,
            project=project,
            configuration=configuration,
            actor=actor,
            **payload.model_dump(),
        )
    )


@router.patch(
    "/{project_id}/pricing/area-rules/{rule_id}",
    response_model=AreaRuleRead,
    summary="Change an area pricing rule of a draft configuration",
)
def update_area_rule(
    rule_id: uuid.UUID,
    payload: AreaRuleUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> AreaRuleRead:
    require_pricing_writer(actor)
    rule = service.get_area_rule(session, project_id=project.id, rule_id=rule_id)
    return AreaRuleRead.model_validate(
        service.update_area_rule(
            session,
            project=project,
            rule=rule,
            actor=actor,
            **payload.model_dump(exclude_unset=True),
        )
    )


@router.get(
    "/{project_id}/pricing/configurations/{configuration_id}/premium-rules",
    response_model=list[PremiumRuleRead],
    summary="List the premium rules of a configuration",
)
def list_premium_rules(
    configuration_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> list[PremiumRuleRead]:
    require_internal_price_reader(actor)
    configuration = _require_configuration(session, project, configuration_id)
    return [
        PremiumRuleRead.model_validate(rule)
        for rule in service.list_premium_rules(session, configuration_id=configuration.id)
    ]


@router.post(
    "/{project_id}/pricing/configurations/{configuration_id}/premium-rules",
    response_model=PremiumRuleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a premium rule",
)
def create_premium_rule(
    configuration_id: uuid.UUID,
    payload: PremiumRuleCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PremiumRuleRead:
    require_pricing_writer(actor)
    configuration = _require_configuration(session, project, configuration_id)
    return PremiumRuleRead.model_validate(
        service.create_premium_rule(
            session,
            project=project,
            configuration=configuration,
            actor=actor,
            **payload.model_dump(),
        )
    )


@router.patch(
    "/{project_id}/pricing/premium-rules/{rule_id}",
    response_model=PremiumRuleRead,
    summary="Change a premium rule of a draft configuration",
)
def update_premium_rule(
    rule_id: uuid.UUID,
    payload: PremiumRuleUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PremiumRuleRead:
    require_pricing_writer(actor)
    rule = service.get_premium_rule(session, project_id=project.id, rule_id=rule_id)
    return PremiumRuleRead.model_validate(
        service.update_premium_rule(
            session,
            project=project,
            rule=rule,
            actor=actor,
            **payload.model_dump(exclude_unset=True),
        )
    )


# --------------------------------------------------------------------------- #
# Escalation
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/pricing/escalation-rules",
    response_model=list[EscalationRuleRead],
    summary="List a project's escalation rules",
)
def list_escalation_rules(
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
    configuration_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[EscalationRuleRead]:
    require_internal_price_reader(actor)
    return [
        EscalationRuleRead.model_validate(rule)
        for rule in service.list_escalation_rules(
            session, project_id=project.id, configuration_id=configuration_id
        )
    ]


@router.post(
    "/{project_id}/pricing/configurations/{configuration_id}/escalation-rules",
    response_model=EscalationRuleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add an escalation rule",
)
def create_escalation_rule(
    configuration_id: uuid.UUID,
    payload: EscalationRuleCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> EscalationRuleRead:
    require_pricing_writer(actor)
    configuration = _require_configuration(session, project, configuration_id)
    return EscalationRuleRead.model_validate(
        service.create_escalation_rule(
            session,
            project=project,
            configuration=configuration,
            actor=actor,
            **payload.model_dump(),
        )
    )


@router.patch(
    "/{project_id}/pricing/escalation-rules/{rule_id}",
    response_model=EscalationRuleRead,
    summary="Change an escalation rule of a draft configuration",
)
def update_escalation_rule(
    rule_id: uuid.UUID,
    payload: EscalationRuleUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> EscalationRuleRead:
    require_pricing_writer(actor)
    rule = service.get_escalation_rule(session, project_id=project.id, rule_id=rule_id)
    return EscalationRuleRead.model_validate(
        service.update_escalation_rule(
            session,
            project=project,
            rule=rule,
            actor=actor,
            **payload.model_dump(exclude_unset=True),
        )
    )


@router.post(
    "/{project_id}/pricing/escalation-rules/{rule_id}/activate",
    response_model=EscalationActivationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record that an escalation is in force",
)
def activate_escalation(
    rule_id: uuid.UUID,
    payload: EscalationActivateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> EscalationActivationRead:
    require_pricing_approver(actor)
    rule = service.get_escalation_rule(session, project_id=project.id, rule_id=rule_id)
    return EscalationActivationRead.model_validate(
        service.activate_escalation(
            session,
            project=project,
            rule=rule,
            actor=actor,
            **payload.model_dump(),
        )
    )


@router.get(
    "/{project_id}/pricing/escalation-activations",
    response_model=list[EscalationActivationRead],
    summary="List escalation activations",
)
def list_activations(
    session: DbSession, actor: ActiveActor, project: PricingProject
) -> list[EscalationActivationRead]:
    require_internal_price_reader(actor)
    return [
        EscalationActivationRead.model_validate(item)
        for item in service.list_activations(session, project_id=project.id)
    ]


@router.post(
    "/{project_id}/pricing/escalation-activations/{activation_id}/reverse",
    response_model=EscalationActivationRead,
    summary="Reverse an escalation activation",
)
def reverse_activation(
    activation_id: uuid.UUID,
    payload: ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> EscalationActivationRead:
    require_pricing_approver(actor)
    activation = service.get_activation(session, project_id=project.id, activation_id=activation_id)
    return EscalationActivationRead.model_validate(
        service.reverse_activation(
            session, project=project, activation=activation, actor=actor, reason=payload.reason
        )
    )


# --------------------------------------------------------------------------- #
# Market benchmarks
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/pricing/market-benchmarks",
    response_model=list[BenchmarkRead],
    summary="List market benchmarks",
)
def list_benchmarks(
    session: DbSession, actor: ActiveActor, project: PricingProject
) -> list[BenchmarkRead]:
    require_internal_price_reader(actor)
    return [
        BenchmarkRead.model_validate(item)
        for item in service.list_benchmarks(session, project_id=project.id)
    ]


@router.post(
    "/{project_id}/pricing/market-benchmarks",
    response_model=BenchmarkRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a market benchmark",
)
def create_benchmark(
    payload: BenchmarkCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> BenchmarkRead:
    require_pricing_writer(actor)
    require_operational_project(project)
    return BenchmarkRead.model_validate(
        service.create_benchmark(session, project=project, actor=actor, **payload.model_dump())
    )


@router.patch(
    "/{project_id}/pricing/market-benchmarks/{benchmark_id}",
    response_model=BenchmarkRead,
    summary="Change a market benchmark",
)
def update_benchmark(
    benchmark_id: uuid.UUID,
    payload: BenchmarkUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> BenchmarkRead:
    require_pricing_writer(actor)
    benchmark = service.get_benchmark(session, project_id=project.id, benchmark_id=benchmark_id)
    return BenchmarkRead.model_validate(
        service.update_benchmark(
            session,
            project=project,
            benchmark=benchmark,
            actor=actor,
            **payload.model_dump(exclude_unset=True),
        )
    )


# --------------------------------------------------------------------------- #
# The price register and one unit's pricing
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/pricing/overview",
    response_model=PricingOverview,
    summary="What this project prices at, and what is outstanding",
)
def read_overview(
    session: DbSession, actor: ActiveActor, project: PricingProject
) -> PricingOverview:
    require_internal_price_reader(actor)
    configuration = service.active_configuration(session, project_id=project.id)
    _, totals = service.price_register(
        session,
        project=project,
        visible_units=visible_unit_ids(session, project_id=project.id, actor=actor),
        limit=1,
    )
    activations = [
        item for item in service.list_activations(session, project_id=project.id) if item.is_active
    ]
    return PricingOverview(
        configuration=(
            PricingConfigurationRead.model_validate(configuration)
            if configuration is not None
            else None
        ),
        currency_id=configuration.pricing_currency_id if configuration else None,
        base_internal_rate=configuration.base_internal_rate if configuration else None,
        active_escalations=len(activations),
        units_total=totals["total"],
        units_priced=totals["priced"],
        units_not_priced=totals["not_priced"],
        units_repricing_required=totals["repricing_required"],
    )


@router.get(
    "/{project_id}/pricing/register",
    response_model=PriceRegister,
    summary="Every unit and its live price",
)
def read_register(
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
    phase_id: Annotated[uuid.UUID | None, Query()] = None,
    building_id: Annotated[uuid.UUID | None, Query()] = None,
    unit_type_code: Annotated[str | None, Query(max_length=64)] = None,
    market_flag: Annotated[str | None, Query(max_length=24)] = None,
    limit: Annotated[int, Query(ge=1, le=_MAX_PAGE)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PriceRegister:
    require_internal_price_reader(actor)
    rows, totals = service.price_register(
        session,
        project=project,
        visible_units=visible_unit_ids(session, project_id=project.id, actor=actor),
        phase_id=phase_id,
        building_id=building_id,
        unit_type_code=unit_type_code,
        market_flag=market_flag,
        limit=limit,
        offset=offset,
    )
    return PriceRegister(
        rows=[
            PriceRegisterRow(
                unit_id=unit.id,
                unit_reference=unit.unit_reference,
                unit_number=unit.unit_number,
                unit_type_code=unit.unit_type_code,
                commercial_status=unit.commercial_status,
                pricing_approved=unit.pricing_approved,
                repricing_required=service.repricing_required(unit, active=version),
                version_id=version.id if version else None,
                version_number=version.version_number if version else None,
                status=version.status if version else None,
                currency_id=version.currency_id if version else None,
                reference_price_ex_tax=version.reference_price_ex_tax if version else None,
                internal_area_snapshot=version.internal_area_snapshot if version else None,
                weighted_area_snapshot=version.weighted_area_snapshot if version else None,
                price_per_internal_area=version.price_per_internal_area if version else None,
                price_per_weighted_area=version.price_per_weighted_area if version else None,
                market_flag=version.market_flag if version else None,
                market_deviation_fraction=(version.market_deviation_fraction if version else None),
            )
            for unit, version in rows
        ],
        total=totals["total"],
        priced=totals["priced"],
        not_priced=totals["not_priced"],
        repricing_required=totals["repricing_required"],
    )


@router.get(
    "/{project_id}/pricing/units/{unit_id}",
    response_model=UnitPricingRead,
    summary="A unit's live price, its history and its waterfall",
)
def read_unit_pricing(
    unit_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> UnitPricingRead:
    unit = require_priceable_unit(session, project=project, unit_id=unit_id, actor=actor)
    internal = sees_internal_prices(actor)
    if not internal:
        require_quote_reader(actor)
    active = service.active_price(session, unit_id=unit.id)
    history = service.list_price_versions(session, unit_id=unit.id, internal=internal)
    return UnitPricingRead(
        unit_id=unit.id,
        unit_reference=unit.unit_reference,
        unit_type_code=unit.unit_type_code,
        pricing_approved=unit.pricing_approved,
        repricing_required=service.repricing_required(unit, active=active),
        has_active_configuration=(
            service.active_configuration(session, project_id=project.id) is not None
        ),
        active_price=_detail(session, active) if active is not None else None,
        history=[PriceVersionRead.model_validate(item) for item in history],
    )


@router.get(
    "/{project_id}/pricing/units/{unit_id}/price-versions",
    response_model=list[PriceVersionRead],
    summary="A unit's price history",
)
def list_unit_price_versions(
    unit_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> list[PriceVersionRead]:
    unit = require_priceable_unit(session, project=project, unit_id=unit_id, actor=actor)
    internal = sees_internal_prices(actor)
    if not internal:
        require_quote_reader(actor)
    return [
        PriceVersionRead.model_validate(item)
        for item in service.list_price_versions(session, unit_id=unit.id, internal=internal)
    ]


@router.post(
    "/{project_id}/pricing/units/{unit_id}/price-versions",
    response_model=PriceVersionDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Draft a price for one unit",
)
def create_price_version(
    unit_id: uuid.UUID,
    payload: PriceVersionCreateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PriceVersionDetail:
    require_pricing_writer(actor)
    unit = require_priceable_unit(session, project=project, unit_id=unit_id, actor=actor)
    body = payload.model_dump()
    upgrades = tuple(
        service.UpgradeInput(code=item["code"], label=item["label"], amount=item["amount"])
        for item in body.pop("paid_upgrades", [])
    )
    version = service.generate_price_version(
        session, project=project, unit=unit, actor=actor, paid_upgrades=upgrades, **body
    )
    return _detail(session, version)


@router.post(
    "/{project_id}/pricing/units/{unit_id}/quote-preview",
    response_model=QuotePreviewRead,
    summary="Model an offer against a unit's live price, writing nothing",
)
def quote_preview(
    unit_id: uuid.UUID,
    payload: QuotePreviewRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> QuotePreviewRead:
    require_quote_reader(actor)
    unit = require_priceable_unit(session, project=project, unit_id=unit_id, actor=actor)
    result = service.quote_preview(
        session, project=project, unit=unit, inputs=payload.model_dump(exclude_unset=True)
    )
    return QuotePreviewRead.model_validate(result)


# --------------------------------------------------------------------------- #
# Bulk pricing
#
# Declared before the ``{version_id}`` routes: FastAPI matches in declaration
# order, and "generate" is not a UUID.
# --------------------------------------------------------------------------- #


def _selected_units(
    session: DbSession, actor: ActorContext, project: Project, payload: BulkGenerateRequest
) -> list[Unit]:
    """The units a bulk request selects, narrowed to what the caller may see.

    A filter narrows; it never widens. An explicit identifier for a unit in a
    phase the caller was not granted is simply not selected, and the count in
    the response says so — which is the same answer they would get by asking
    for that unit directly.
    """
    if not any(
        (
            payload.unit_ids,
            payload.phase_id,
            payload.building_id,
            payload.unit_type_code,
            payload.commercial_status,
        )
    ):
        raise ValidationError(
            "Name the units to price: identifiers, a phase, a building, a unit type "
            "or a commercial status."
        )
    statement = (
        select(Unit)
        .join(Floor, Floor.id == Unit.floor_id)
        .join(Building, Building.id == Floor.building_id)
        .where(Unit.project_id == project.id, Unit.is_active.is_(True))
    )
    if payload.unit_ids:
        statement = statement.where(Unit.id.in_(payload.unit_ids))
    if payload.phase_id is not None:
        statement = statement.where(Building.phase_id == payload.phase_id)
    if payload.building_id is not None:
        statement = statement.where(Floor.building_id == payload.building_id)
    if payload.unit_type_code is not None:
        statement = statement.where(Unit.unit_type_code == payload.unit_type_code)
    if payload.commercial_status is not None:
        statement = statement.where(Unit.commercial_status == payload.commercial_status)
    statement = visible_units_for_pricing(statement, session, project_id=project.id, actor=actor)
    return list(session.scalars(statement.order_by(Unit.id)))


@router.post(
    "/{project_id}/pricing/price-versions/generate",
    response_model=list[PriceVersionRead],
    status_code=status.HTTP_201_CREATED,
    summary="Draft prices for a selection of units, all of them or none",
)
def generate_price_versions(
    payload: BulkGenerateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> list[PriceVersionRead]:
    require_pricing_writer(actor)
    units = _selected_units(session, actor, project, payload)
    versions = service.generate_price_versions(
        session,
        project=project,
        units=units,
        actor=actor,
        valid_from=payload.valid_from,
        change_reason=payload.change_reason,
    )
    return [PriceVersionRead.model_validate(item) for item in versions]


def _selected_versions(
    session: DbSession, actor: ActorContext, project: Project, version_ids: list[uuid.UUID]
) -> list[UnitPriceVersion]:
    found = [
        _require_version(session, project, actor, version_id, internal=True)
        for version_id in version_ids
    ]
    return found


@router.post(
    "/{project_id}/pricing/price-versions/submit",
    response_model=list[PriceVersionRead],
    summary="Submit a selection of draft prices",
)
def bulk_submit(
    payload: BulkVersionRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> list[PriceVersionRead]:
    require_pricing_writer(actor)
    versions = _selected_versions(session, actor, project, payload.version_ids)
    return [
        PriceVersionRead.model_validate(item)
        for item in service.bulk_transition(
            session,
            project=project,
            versions=versions,
            actor=actor,
            action="submit",
            reason=payload.reason,
        )
    ]


@router.post(
    "/{project_id}/pricing/price-versions/approve",
    response_model=list[PriceVersionRead],
    summary="Approve a selection of submitted prices",
)
def bulk_approve(
    payload: BulkVersionRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> list[PriceVersionRead]:
    require_pricing_approver(actor)
    versions = _selected_versions(session, actor, project, payload.version_ids)
    return [
        PriceVersionRead.model_validate(item)
        for item in service.bulk_transition(
            session,
            project=project,
            versions=versions,
            actor=actor,
            action="approve",
            reason=payload.reason,
        )
    ]


@router.post(
    "/{project_id}/pricing/price-versions/activate",
    response_model=list[PriceVersionRead],
    summary="Activate a selection of approved prices",
)
def bulk_activate(
    payload: BulkVersionRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> list[PriceVersionRead]:
    require_pricing_approver(actor)
    versions = _selected_versions(session, actor, project, payload.version_ids)
    return [
        PriceVersionRead.model_validate(item)
        for item in service.bulk_transition(
            session,
            project=project,
            versions=versions,
            actor=actor,
            action="activate",
            reason=payload.reason,
            valid_from=payload.valid_from,
        )
    ]


# --------------------------------------------------------------------------- #
# One price version
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/pricing/price-versions/{version_id}",
    response_model=PriceVersionDetail,
    summary="Read a price version and its waterfall",
)
def read_price_version(
    version_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PriceVersionDetail:
    return _detail(session, _require_version(session, project, actor, version_id))


@router.patch(
    "/{project_id}/pricing/price-versions/{version_id}",
    response_model=PriceVersionDetail,
    summary="Change a draft price version",
)
def update_price_version(
    version_id: uuid.UUID,
    payload: PriceVersionUpdateRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PriceVersionDetail:
    require_pricing_writer(actor)
    version = _require_version(session, project, actor, version_id, internal=True)
    body = payload.model_dump(exclude_unset=True)
    updated = service.update_price_version(
        session,
        project=project,
        version=version,
        actor=actor,
        valid_from=body.get("valid_from"),
        change_reason=body.get("change_reason"),
        overrides=body.get("overrides"),
    )
    return _detail(session, updated)


@router.post(
    "/{project_id}/pricing/price-versions/{version_id}/submit",
    response_model=PriceVersionRead,
    summary="Submit a draft price for approval",
)
def submit_price_version(
    version_id: uuid.UUID,
    payload: OptionalReasonRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PriceVersionRead:
    require_pricing_writer(actor)
    version = _require_version(session, project, actor, version_id, internal=True)
    return PriceVersionRead.model_validate(
        service.submit_price_version(
            session, project=project, version=version, actor=actor, change_reason=payload.reason
        )
    )


@router.post(
    "/{project_id}/pricing/price-versions/{version_id}/return",
    response_model=PriceVersionRead,
    summary="Return a submitted price to its author",
)
def return_price_version(
    version_id: uuid.UUID,
    payload: ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PriceVersionRead:
    require_pricing_approver(actor)
    version = _require_version(session, project, actor, version_id, internal=True)
    return PriceVersionRead.model_validate(
        service.return_price_version(
            session, project=project, version=version, actor=actor, reason=payload.reason
        )
    )


@router.post(
    "/{project_id}/pricing/price-versions/{version_id}/approve",
    response_model=PriceVersionRead,
    summary="Approve a submitted price",
)
def approve_price_version(
    version_id: uuid.UUID,
    payload: ReasonRequest,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PriceVersionRead:
    require_pricing_approver(actor)
    version = _require_version(session, project, actor, version_id, internal=True)
    return PriceVersionRead.model_validate(
        service.approve_price_version(
            session, project=project, version=version, actor=actor, reason=payload.reason
        )
    )


@router.post(
    "/{project_id}/pricing/price-versions/{version_id}/activate",
    response_model=PriceVersionRead,
    summary="Make an approved price the unit's list price",
)
def activate_price_version(
    version_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    project: PricingProject,
) -> PriceVersionRead:
    require_pricing_approver(actor)
    version = _require_version(session, project, actor, version_id, internal=True)
    return PriceVersionRead.model_validate(
        service.activate_price_version(session, project=project, version=version, actor=actor)
    )
