"""
settings.service

Business logic for the Settings domain.

Enforces single-default invariants: at most one PricingPolicy and one
CommissionPolicy may be flagged is_default=True at any time.  When a
new or updated policy sets is_default=True, any existing default is
cleared first.

ProjectTemplate FK references are validated: if a pricing or commission
policy ID is supplied it must exist in the database.
"""

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.settings.repository import (
    CommissionPolicyRepository,
    PricingPolicyRepository,
    ProjectTemplateRepository,
)
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


class SettingsService:
    def __init__(self, db: Session) -> None:
        self.pricing_repo = PricingPolicyRepository(db)
        self.commission_repo = CommissionPolicyRepository(db)
        self.template_repo = ProjectTemplateRepository(db)
        self.db = db

    # ── PricingPolicy ─────────────────────────────────────────────────────────

    def create_pricing_policy(
        self, data: PricingPolicyCreate
    ) -> PricingPolicyResponse:
        if self.pricing_repo.get_by_name(data.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A pricing policy named '{data.name}' already exists.",
            )
        if data.is_default:
            self.pricing_repo.clear_default()
        try:
            policy = self.pricing_repo.create(data)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A pricing policy named '{data.name}' already exists.",
            )
        return PricingPolicyResponse.model_validate(policy)

    def list_pricing_policies(
        self,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> PricingPolicyList:
        items = self.pricing_repo.list(is_active=is_active, skip=skip, limit=limit)
        total = self.pricing_repo.count(is_active=is_active)
        return PricingPolicyList(
            total=total,
            items=[PricingPolicyResponse.model_validate(p) for p in items],
        )

    def get_pricing_policy(self, policy_id: str) -> PricingPolicyResponse:
        policy = self.pricing_repo.get_by_id(policy_id)
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pricing policy '{policy_id}' not found.",
            )
        return PricingPolicyResponse.model_validate(policy)

    def update_pricing_policy(
        self, policy_id: str, data: PricingPolicyUpdate
    ) -> PricingPolicyResponse:
        policy = self.pricing_repo.get_by_id(policy_id)
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pricing policy '{policy_id}' not found.",
            )
        # Check name uniqueness if it is changing
        if data.name is not None and data.name != policy.name:
            if self.pricing_repo.get_by_name(data.name):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A pricing policy named '{data.name}' already exists.",
                )
        # Enforce single-default invariant
        if data.is_default is True and not policy.is_default:
            self.pricing_repo.clear_default()
        try:
            updated = self.pricing_repo.update(policy, data)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A pricing policy named '{data.name}' already exists.",
            )
        return PricingPolicyResponse.model_validate(updated)

    def delete_pricing_policy(self, policy_id: str) -> None:
        policy = self.pricing_repo.get_by_id(policy_id)
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pricing policy '{policy_id}' not found.",
            )
        self.pricing_repo.delete(policy)

    # ── CommissionPolicy ──────────────────────────────────────────────────────

    def create_commission_policy(
        self, data: CommissionPolicyCreate
    ) -> CommissionPolicyResponse:
        if self.commission_repo.get_by_name(data.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A commission policy named '{data.name}' already exists.",
            )
        if data.is_default:
            self.commission_repo.clear_default()
        try:
            policy = self.commission_repo.create(data)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A commission policy named '{data.name}' already exists.",
            )
        return CommissionPolicyResponse.model_validate(policy)

    def list_commission_policies(
        self,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> CommissionPolicyList:
        items = self.commission_repo.list(is_active=is_active, skip=skip, limit=limit)
        total = self.commission_repo.count(is_active=is_active)
        return CommissionPolicyList(
            total=total,
            items=[CommissionPolicyResponse.model_validate(p) for p in items],
        )

    def get_commission_policy(self, policy_id: str) -> CommissionPolicyResponse:
        policy = self.commission_repo.get_by_id(policy_id)
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Commission policy '{policy_id}' not found.",
            )
        return CommissionPolicyResponse.model_validate(policy)

    def update_commission_policy(
        self, policy_id: str, data: CommissionPolicyUpdate
    ) -> CommissionPolicyResponse:
        policy = self.commission_repo.get_by_id(policy_id)
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Commission policy '{policy_id}' not found.",
            )
        if data.name is not None and data.name != policy.name:
            if self.commission_repo.get_by_name(data.name):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A commission policy named '{data.name}' already exists.",
                )
        if data.is_default is True and not policy.is_default:
            self.commission_repo.clear_default()
        try:
            updated = self.commission_repo.update(policy, data)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A commission policy named '{data.name}' already exists.",
            )
        return CommissionPolicyResponse.model_validate(updated)

    def delete_commission_policy(self, policy_id: str) -> None:
        policy = self.commission_repo.get_by_id(policy_id)
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Commission policy '{policy_id}' not found.",
            )
        self.commission_repo.delete(policy)

    # ── ProjectTemplate ───────────────────────────────────────────────────────

    def create_project_template(
        self, data: ProjectTemplateCreate
    ) -> ProjectTemplateResponse:
        if self.template_repo.get_by_name(data.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A project template named '{data.name}' already exists.",
            )
        self._validate_template_refs(
            data.default_pricing_policy_id,
            data.default_commission_policy_id,
        )
        try:
            template = self.template_repo.create(data)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A project template named '{data.name}' already exists.",
            )
        return ProjectTemplateResponse.model_validate(template)

    def list_project_templates(
        self,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> ProjectTemplateList:
        items = self.template_repo.list(is_active=is_active, skip=skip, limit=limit)
        total = self.template_repo.count(is_active=is_active)
        return ProjectTemplateList(
            total=total,
            items=[ProjectTemplateResponse.model_validate(t) for t in items],
        )

    def get_project_template(self, template_id: str) -> ProjectTemplateResponse:
        template = self.template_repo.get_by_id(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project template '{template_id}' not found.",
            )
        return ProjectTemplateResponse.model_validate(template)

    def update_project_template(
        self, template_id: str, data: ProjectTemplateUpdate
    ) -> ProjectTemplateResponse:
        template = self.template_repo.get_by_id(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project template '{template_id}' not found.",
            )
        if data.name is not None and data.name != template.name:
            if self.template_repo.get_by_name(data.name):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A project template named '{data.name}' already exists.",
                )
        # Validate FK references when they are explicitly provided in the patch
        update_fields = data.model_dump(exclude_unset=True)
        pricing_id = update_fields.get(
            "default_pricing_policy_id", template.default_pricing_policy_id
        )
        commission_id = update_fields.get(
            "default_commission_policy_id", template.default_commission_policy_id
        )
        # Only validate if the caller actually changed the FK fields
        if (
            "default_pricing_policy_id" in update_fields
            or "default_commission_policy_id" in update_fields
        ):
            self._validate_template_refs(pricing_id, commission_id)
        try:
            updated = self.template_repo.update(template, data)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A project template named '{data.name}' already exists.",
            )
        return ProjectTemplateResponse.model_validate(updated)

    def delete_project_template(self, template_id: str) -> None:
        template = self.template_repo.get_by_id(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project template '{template_id}' not found.",
            )
        self.template_repo.delete(template)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _validate_template_refs(
        self,
        pricing_policy_id: str | None,
        commission_policy_id: str | None,
    ) -> None:
        if pricing_policy_id is not None:
            if not self.pricing_repo.get_by_id(pricing_policy_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Pricing policy '{pricing_policy_id}' not found.",
                )
        if commission_policy_id is not None:
            if not self.commission_repo.get_by_id(commission_policy_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Commission policy '{commission_policy_id}' not found.",
                )
