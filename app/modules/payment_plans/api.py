"""
payment_plans.api

REST endpoints for payment plan templates and contract schedule generation.

Router prefix: /payment-plans
Full path:     /api/v1/payment-plans/...

Endpoints
---------
Templates
  POST   /templates                          — create a template
  GET    /templates                          — list templates
  GET    /templates/{template_id}            — get a template
  PATCH  /templates/{template_id}            — update a template

Payment plan creation (PR029 simplified interface)
  POST   /                                   — create a payment plan for a contract
  GET    /{plan_id}                          — get a specific schedule item by ID

Schedule generation (advanced)
  POST   /generate                           — generate schedule for a contract
  GET    /contracts/{contract_id}/schedule   — retrieve schedule for a contract
  POST   /contracts/{contract_id}/regenerate — replace schedule for a contract

Contract-scoped aliases (PR029 blueprint routes)
  GET    /contracts/{contract_id}/payment-plan  — get the payment plan for a contract
  GET    /contracts/{contract_id}/installments  — list installments for a contract
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.payment_plans.schemas import (
    PaymentPlanCreate,
    PaymentPlanGenerateRequest,
    PaymentPlanResponse,
    PaymentPlanTemplateCreate,
    PaymentPlanTemplateList,
    PaymentPlanTemplateResponse,
    PaymentPlanTemplateUpdate,
    PaymentScheduleListResponse,
    PaymentScheduleResponse,
)
from app.modules.payment_plans.service import PaymentPlanService

router = APIRouter(prefix="/payment-plans", tags=["payment-plans"])


def get_service(db: Session = Depends(get_db)) -> PaymentPlanService:
    return PaymentPlanService(db)


# ---------------------------------------------------------------------------
# PR029 — simplified payment plan endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=PaymentPlanResponse, status_code=201)
def create_payment_plan(
    data: PaymentPlanCreate,
    service: Annotated[PaymentPlanService, Depends(get_service)],
) -> PaymentPlanResponse:
    """Create a payment plan for a contract.

    Generates the installment schedule immediately from the provided parameters.
    A contract can only have one active payment plan; use the regenerate endpoint
    to replace an existing schedule.
    """
    return service.create_payment_plan(data)


# ---------------------------------------------------------------------------
# Template endpoints
# ---------------------------------------------------------------------------


@router.post("/templates", response_model=PaymentPlanTemplateResponse, status_code=201)
def create_template(
    data: PaymentPlanTemplateCreate,
    service: Annotated[PaymentPlanService, Depends(get_service)],
) -> PaymentPlanTemplateResponse:
    """Create a new payment plan template."""
    return service.create_template(data)


@router.get("/templates", response_model=PaymentPlanTemplateList)
def list_templates(
    service: Annotated[PaymentPlanService, Depends(get_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> PaymentPlanTemplateList:
    """List all payment plan templates."""
    return service.list_templates(skip=skip, limit=limit)


@router.get("/templates/{template_id}", response_model=PaymentPlanTemplateResponse)
def get_template(
    template_id: str,
    service: Annotated[PaymentPlanService, Depends(get_service)],
) -> PaymentPlanTemplateResponse:
    """Get a payment plan template by ID."""
    return service.get_template(template_id)


@router.patch("/templates/{template_id}", response_model=PaymentPlanTemplateResponse)
def update_template(
    template_id: str,
    data: PaymentPlanTemplateUpdate,
    service: Annotated[PaymentPlanService, Depends(get_service)],
) -> PaymentPlanTemplateResponse:
    """Partially update a payment plan template."""
    return service.update_template(template_id, data)


# ---------------------------------------------------------------------------
# Schedule endpoints
# ---------------------------------------------------------------------------


@router.post("/generate", response_model=PaymentScheduleListResponse, status_code=201)
def generate_schedule(
    request: PaymentPlanGenerateRequest,
    service: Annotated[PaymentPlanService, Depends(get_service)],
) -> PaymentScheduleListResponse:
    """Generate and persist a payment schedule for a contract."""
    return service.generate_schedule_for_contract(request)


@router.get(
    "/contracts/{contract_id}/schedule",
    response_model=PaymentScheduleListResponse,
)
def get_schedule(
    contract_id: str,
    service: Annotated[PaymentPlanService, Depends(get_service)],
) -> PaymentScheduleListResponse:
    """Retrieve the payment schedule for a contract."""
    return service.get_schedule_for_contract(contract_id)


@router.post(
    "/contracts/{contract_id}/regenerate",
    response_model=PaymentScheduleListResponse,
    status_code=201,
)
def regenerate_schedule(
    contract_id: str,
    request: PaymentPlanGenerateRequest,
    service: Annotated[PaymentPlanService, Depends(get_service)],
) -> PaymentScheduleListResponse:
    """Replace an existing payment schedule with a freshly generated one."""
    return service.regenerate_schedule_for_contract(contract_id, request)


# ---------------------------------------------------------------------------
# Contract-scoped alias endpoints (PR029 blueprint)
# ---------------------------------------------------------------------------


@router.get(
    "/contracts/{contract_id}/payment-plan",
    response_model=PaymentPlanResponse,
)
def get_contract_payment_plan(
    contract_id: str,
    service: Annotated[PaymentPlanService, Depends(get_service)],
) -> PaymentPlanResponse:
    """Get the payment plan for a contract."""
    return service.get_contract_payment_plan(contract_id)


@router.get(
    "/contracts/{contract_id}/installments",
    response_model=PaymentScheduleListResponse,
)
def list_contract_installments(
    contract_id: str,
    service: Annotated[PaymentPlanService, Depends(get_service)],
) -> PaymentScheduleListResponse:
    """List all installments for a contract."""
    return service.list_contract_installments(contract_id)


# NOTE: This parameterised route must be declared AFTER all routes with static
# path segments (/templates, /generate, /contracts/…) so that FastAPI's route
# matching prefers the more-specific paths.
@router.get("/{plan_id}", response_model=PaymentScheduleResponse)
def get_payment_plan_item(
    plan_id: str,
    service: Annotated[PaymentPlanService, Depends(get_service)],
) -> PaymentScheduleResponse:
    """Get a specific payment schedule item by ID."""
    return service.get_plan(plan_id)
