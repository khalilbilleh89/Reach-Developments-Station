"""
settings.api

CRUD API router for the Settings business domain.

Endpoints — PricingPolicy
  POST   /api/v1/settings/pricing-policies
  GET    /api/v1/settings/pricing-policies
  GET    /api/v1/settings/pricing-policies/{policy_id}
  PATCH  /api/v1/settings/pricing-policies/{policy_id}
  DELETE /api/v1/settings/pricing-policies/{policy_id}

Endpoints — CommissionPolicy
  POST   /api/v1/settings/commission-policies
  GET    /api/v1/settings/commission-policies
  GET    /api/v1/settings/commission-policies/{policy_id}
  PATCH  /api/v1/settings/commission-policies/{policy_id}
  DELETE /api/v1/settings/commission-policies/{policy_id}

Endpoints — ProjectTemplate
  POST   /api/v1/settings/project-templates
  GET    /api/v1/settings/project-templates
  GET    /api/v1/settings/project-templates/{template_id}
  PATCH  /api/v1/settings/project-templates/{template_id}
  DELETE /api/v1/settings/project-templates/{template_id}
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.security import get_current_user_payload
from app.modules.settings.schemas import (
    CommissionPolicyCreate,
    CommissionPolicyList,
    CommissionPolicyResponse,
    CommissionPolicyUpdate,
    PricingPolicyCreate,
    PricingPolicyList,
    PricingPolicyResponse,
    PricingPolicyUpdate,
    ProjectTemplateCreate,
    ProjectTemplateList,
    ProjectTemplateResponse,
    ProjectTemplateUpdate,
)
from app.modules.settings.service import SettingsService

router = APIRouter(prefix="/settings", tags=["Settings"], dependencies=[Depends(get_current_user_payload)])

DbDep = Annotated[Session, Depends(get_db)]


def _service(db: DbDep) -> SettingsService:
    return SettingsService(db)


ServiceDep = Annotated[SettingsService, Depends(_service)]


# ---------------------------------------------------------------------------
# PricingPolicy endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/pricing-policies",
    response_model=PricingPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pricing_policy(
    data: PricingPolicyCreate,
    service: ServiceDep,
) -> PricingPolicyResponse:
    return service.create_pricing_policy(data)


@router.get("/pricing-policies", response_model=PricingPolicyList)
def list_pricing_policies(
    service: ServiceDep,
    is_active: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> PricingPolicyList:
    return service.list_pricing_policies(is_active=is_active, skip=skip, limit=limit)


@router.get(
    "/pricing-policies/{policy_id}", response_model=PricingPolicyResponse
)
def get_pricing_policy(
    policy_id: str,
    service: ServiceDep,
) -> PricingPolicyResponse:
    return service.get_pricing_policy(policy_id)


@router.patch(
    "/pricing-policies/{policy_id}", response_model=PricingPolicyResponse
)
def update_pricing_policy(
    policy_id: str,
    data: PricingPolicyUpdate,
    service: ServiceDep,
) -> PricingPolicyResponse:
    return service.update_pricing_policy(policy_id, data)


@router.delete(
    "/pricing-policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_pricing_policy(
    policy_id: str,
    service: ServiceDep,
) -> Response:
    service.delete_pricing_policy(policy_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# CommissionPolicy endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/commission-policies",
    response_model=CommissionPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_commission_policy(
    data: CommissionPolicyCreate,
    service: ServiceDep,
) -> CommissionPolicyResponse:
    return service.create_commission_policy(data)


@router.get("/commission-policies", response_model=CommissionPolicyList)
def list_commission_policies(
    service: ServiceDep,
    is_active: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> CommissionPolicyList:
    return service.list_commission_policies(
        is_active=is_active, skip=skip, limit=limit
    )


@router.get(
    "/commission-policies/{policy_id}", response_model=CommissionPolicyResponse
)
def get_commission_policy(
    policy_id: str,
    service: ServiceDep,
) -> CommissionPolicyResponse:
    return service.get_commission_policy(policy_id)


@router.patch(
    "/commission-policies/{policy_id}", response_model=CommissionPolicyResponse
)
def update_commission_policy(
    policy_id: str,
    data: CommissionPolicyUpdate,
    service: ServiceDep,
) -> CommissionPolicyResponse:
    return service.update_commission_policy(policy_id, data)


@router.delete(
    "/commission-policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_commission_policy(
    policy_id: str,
    service: ServiceDep,
) -> Response:
    service.delete_commission_policy(policy_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# ProjectTemplate endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/project-templates",
    response_model=ProjectTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_template(
    data: ProjectTemplateCreate,
    service: ServiceDep,
) -> ProjectTemplateResponse:
    return service.create_project_template(data)


@router.get("/project-templates", response_model=ProjectTemplateList)
def list_project_templates(
    service: ServiceDep,
    is_active: Optional[bool] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> ProjectTemplateList:
    return service.list_project_templates(
        is_active=is_active, skip=skip, limit=limit
    )


@router.get(
    "/project-templates/{template_id}", response_model=ProjectTemplateResponse
)
def get_project_template(
    template_id: str,
    service: ServiceDep,
) -> ProjectTemplateResponse:
    return service.get_project_template(template_id)


@router.patch(
    "/project-templates/{template_id}", response_model=ProjectTemplateResponse
)
def update_project_template(
    template_id: str,
    data: ProjectTemplateUpdate,
    service: ServiceDep,
) -> ProjectTemplateResponse:
    return service.update_project_template(template_id, data)


@router.delete(
    "/project-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_project_template(
    template_id: str,
    service: ServiceDep,
) -> Response:
    service.delete_project_template(template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
