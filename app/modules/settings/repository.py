"""
settings.repository

Database access layer for the Settings domain.

Provides simple CRUD operations for PricingPolicy, CommissionPolicy, and
ProjectTemplate.  All business-rule enforcement lives in the service layer.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.modules.settings.models import (
    CommissionPolicy,
    PricingPolicy,
    ProjectTemplate,
)
from app.modules.settings.schemas import (
    CommissionPolicyCreate,
    CommissionPolicyUpdate,
    PricingPolicyCreate,
    PricingPolicyUpdate,
    ProjectTemplateCreate,
    ProjectTemplateUpdate,
)


class PricingPolicyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: PricingPolicyCreate) -> PricingPolicy:
        policy = PricingPolicy(**data.model_dump())
        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def get_by_id(self, policy_id: str) -> Optional[PricingPolicy]:
        return self.db.get(PricingPolicy, policy_id)

    def get_by_name(self, name: str) -> Optional[PricingPolicy]:
        return (
            self.db.query(PricingPolicy)
            .filter(PricingPolicy.name == name)
            .first()
        )

    def get_default(self) -> Optional[PricingPolicy]:
        return (
            self.db.query(PricingPolicy)
            .filter(PricingPolicy.is_default.is_(True))
            .first()
        )

    def list(
        self,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[PricingPolicy]:
        q = self.db.query(PricingPolicy)
        if is_active is not None:
            q = q.filter(PricingPolicy.is_active == is_active)
        return q.order_by(PricingPolicy.name).offset(skip).limit(limit).all()

    def count(self, is_active: Optional[bool] = None) -> int:
        q = self.db.query(PricingPolicy)
        if is_active is not None:
            q = q.filter(PricingPolicy.is_active == is_active)
        return q.count()

    def update(self, policy: PricingPolicy, data: PricingPolicyUpdate) -> PricingPolicy:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(policy, field, value)
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def clear_default(self) -> None:
        """Unset is_default on all pricing policies."""
        self.db.query(PricingPolicy).filter(
            PricingPolicy.is_default.is_(True)
        ).update({"is_default": False}, synchronize_session=False)
        self.db.commit()

    def delete(self, policy: PricingPolicy) -> None:
        self.db.delete(policy)
        self.db.commit()


class CommissionPolicyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: CommissionPolicyCreate) -> CommissionPolicy:
        policy = CommissionPolicy(**data.model_dump())
        self.db.add(policy)
        self.db.flush()
        self.db.refresh(policy)
        return policy

    def get_by_id(self, policy_id: str) -> Optional[CommissionPolicy]:
        return self.db.get(CommissionPolicy, policy_id)

    def get_by_name(self, name: str) -> Optional[CommissionPolicy]:
        return (
            self.db.query(CommissionPolicy)
            .filter(CommissionPolicy.name == name)
            .first()
        )

    def get_default(self) -> Optional[CommissionPolicy]:
        return (
            self.db.query(CommissionPolicy)
            .filter(CommissionPolicy.is_default.is_(True))
            .first()
        )

    def list(
        self,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[CommissionPolicy]:
        q = self.db.query(CommissionPolicy)
        if is_active is not None:
            q = q.filter(CommissionPolicy.is_active == is_active)
        return q.order_by(CommissionPolicy.name).offset(skip).limit(limit).all()

    def count(self, is_active: Optional[bool] = None) -> int:
        q = self.db.query(CommissionPolicy)
        if is_active is not None:
            q = q.filter(CommissionPolicy.is_active == is_active)
        return q.count()

    def update(
        self, policy: CommissionPolicy, data: CommissionPolicyUpdate
    ) -> CommissionPolicy:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(policy, field, value)
        self.db.flush()
        self.db.refresh(policy)
        return policy

    def clear_default(self) -> None:
        """Unset is_default on all commission policies."""
        self.db.query(CommissionPolicy).filter(
            CommissionPolicy.is_default.is_(True)
        ).update({"is_default": False})

    def delete(self, policy: CommissionPolicy) -> None:
        self.db.delete(policy)
        self.db.flush()


class ProjectTemplateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: ProjectTemplateCreate) -> ProjectTemplate:
        template = ProjectTemplate(**data.model_dump())
        self.db.add(template)
        self.db.flush()
        self.db.refresh(template)
        return template

    def get_by_id(self, template_id: str) -> Optional[ProjectTemplate]:
        return self.db.get(ProjectTemplate, template_id)

    def get_by_name(self, name: str) -> Optional[ProjectTemplate]:
        return (
            self.db.query(ProjectTemplate)
            .filter(ProjectTemplate.name == name)
            .first()
        )

    def list(
        self,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ProjectTemplate]:
        q = self.db.query(ProjectTemplate)
        if is_active is not None:
            q = q.filter(ProjectTemplate.is_active == is_active)
        return q.order_by(ProjectTemplate.name).offset(skip).limit(limit).all()

    def count(self, is_active: Optional[bool] = None) -> int:
        q = self.db.query(ProjectTemplate)
        if is_active is not None:
            q = q.filter(ProjectTemplate.is_active == is_active)
        return q.count()

    def update(
        self, template: ProjectTemplate, data: ProjectTemplateUpdate
    ) -> ProjectTemplate:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(template, field, value)
        self.db.flush()
        self.db.refresh(template)
        return template

    def delete(self, template: ProjectTemplate) -> None:
        self.db.delete(template)
        self.db.flush()
