"""Project-scoped company commands with serialized writes and retained removal."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects.company_models import (
    CompanyBankAccount,
    CompanyDocument,
    CompanyLogo,
    ProjectCompany,
)
from app.modules.projects.company_schemas import BankAccountRead, CompanyDetail
from app.modules.projects.models import Project
from app.modules.projects.permissions import FINANCIAL_ROLES, whole_project_ids
from app.modules.settings.models import Currency

COMPANY_READERS = FINANCIAL_ROLES
COMPANY_WRITERS = frozenset({"system_admin", "project_manager", "finance"})


def scope(
    session: Session, project_id: uuid.UUID, actor: ActorContext, *, write: bool = False
) -> None:
    query = select(Project).where(
        Project.id == project_id, Project.id.in_(whole_project_ids(actor))
    )
    if write:
        query = query.with_for_update().execution_options(populate_existing=True)
    if session.scalars(query).first() is None:
        raise NotFoundError("Project not found.")
    if not actor.is_system_admin and not actor.role_keys.intersection(
        COMPANY_WRITERS if write else COMPANY_READERS
    ):
        raise PermissionDeniedError("You do not have permission to access company details.")


def company(session: Session, project_id: uuid.UUID, company_id: uuid.UUID) -> ProjectCompany:
    row = session.scalars(
        select(ProjectCompany)
        .where(
            ProjectCompany.id == company_id,
            ProjectCompany.project_id == project_id,
            ProjectCompany.is_deleted.is_(False),
        )
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFoundError("Company not found.")
    return row


def account(session: Session, company_id: uuid.UUID, account_id: uuid.UUID) -> CompanyBankAccount:
    row = session.scalars(
        select(CompanyBankAccount)
        .where(
            CompanyBankAccount.id == account_id,
            CompanyBankAccount.company_id == company_id,
            CompanyBankAccount.is_deleted.is_(False),
        )
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise NotFoundError("Bank account not found.")
    return row


def detail(session: Session, row: ProjectCompany, actor: ActorContext) -> CompanyDetail:
    accounts = session.scalars(
        select(CompanyBankAccount)
        .where(
            CompanyBankAccount.company_id == row.id,
            CompanyBankAccount.is_deleted.is_(False),
        )
        .order_by(CompanyBankAccount.created_at, CompanyBankAccount.id)
    ).all()
    if not can_access_bank(actor):
        accounts = []
    return CompanyDetail(
        **{
            key: getattr(row, key)
            for key in CompanyDetail.model_fields
            if key not in {"bank_accounts", "logo_id"}
        },
        bank_accounts=[BankAccountRead.model_validate(item) for item in accounts],
        logo_id=session.scalar(
            select(CompanyLogo.id).where(
                CompanyLogo.company_id == row.id, CompanyLogo.is_deleted.is_(False)
            )
        ),
    )


def can_access_bank(actor: ActorContext) -> bool:
    return actor.is_system_admin or bool(actor.role_keys.intersection({"system_admin", "finance"}))


def bank_permission(actor: ActorContext) -> None:
    if not can_access_bank(actor):
        raise PermissionDeniedError(
            "Bank details are available to finance and administrators only."
        )


def validate_profile(session: Session, row: ProjectCompany | CompanyBankAccount) -> None:
    if isinstance(row, ProjectCompany):
        seen = {row.id}
        related_id = row.related_company_id
        while related_id is not None:
            if related_id in seen:
                raise ValidationError(
                    "Company relationships must not link a company to itself or form a cycle."
                )
            seen.add(related_id)
            related = company(session, row.project_id, related_id)
            related_id = related.related_company_id
    else:
        if row.currency_code and not session.scalar(
            select(Currency.id).where(Currency.code == row.currency_code)
        ):
            raise ValidationError("Select a registered currency.")
        if row.default_for_payments:
            if row.status == "inactive":
                raise ValidationError("An inactive bank account cannot be the payment default.")
            existing = session.scalar(
                select(CompanyBankAccount.id).where(
                    CompanyBankAccount.company_id == row.company_id,
                    CompanyBankAccount.id != row.id,
                    CompanyBankAccount.is_deleted.is_(False),
                    CompanyBankAccount.default_for_payments.is_(True),
                )
            )
            if existing:
                raise ConflictError("Clear the existing default account before choosing another.")


def snapshot(row: ProjectCompany | CompanyBankAccount) -> dict:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def save(
    session: Session,
    row: ProjectCompany | CompanyBankAccount,
    values: dict,
    actor: ActorContext,
    *,
    creating: bool,
) -> None:
    before = None if creating else snapshot(row)
    if isinstance(row, ProjectCompany):
        if values.get("no_related_company") and values.get("related_company_id"):
            raise ValidationError("Choose either a related company or no related company.")
        if values.get("no_related_company"):
            row.related_company_id = None
        elif "related_company_id" in values:
            row.no_related_company = False
    for key, value in values.items():
        setattr(row, key, value.strip() or None if isinstance(value, str) else value)
    with session.no_autoflush:
        validate_profile(session, row)
    if creating:
        session.add(row)
    session.flush()
    record_event(
        session,
        action="create" if creating else "update",
        entity_type="project_company"
        if isinstance(row, ProjectCompany)
        else "company_bank_account",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=snapshot(row),
    )
    session.commit()


def remove(
    session: Session, row: ProjectCompany | CompanyBankAccount, actor: ActorContext, reason: str
) -> None:
    if not reason.strip():
        raise ValidationError("A reason for deletion is required.")
    if (
        isinstance(row, ProjectCompany)
        and session.scalars(
            select(CompanyBankAccount.id).where(
                CompanyBankAccount.company_id == row.id,
                CompanyBankAccount.is_deleted.is_(False),
            )
        ).first()
        is not None
    ):
        raise ConflictError("Delete this company's bank accounts before deleting the company.")
    if (
        isinstance(row, ProjectCompany)
        and session.scalars(
            select(CompanyDocument.id).where(
                CompanyDocument.company_id == row.id, CompanyDocument.is_deleted.is_(False)
            )
        ).first()
        is not None
    ):
        raise ConflictError("Delete this company's documents before deleting the company.")
    if isinstance(row, ProjectCompany):
        if session.scalar(
            select(ProjectCompany.id).where(
                ProjectCompany.related_company_id == row.id, ProjectCompany.is_deleted.is_(False)
            )
        ):
            raise ConflictError("Unlink related companies before deleting this company.")
        if session.scalar(
            select(CompanyLogo.id).where(
                CompanyLogo.company_id == row.id, CompanyLogo.is_deleted.is_(False)
            )
        ):
            raise ConflictError("Delete this company's logo before deleting the company.")
    before = snapshot(row)
    row.is_deleted = True
    session.flush()
    record_event(
        session,
        action="delete",
        entity_type="project_company"
        if isinstance(row, ProjectCompany)
        else "company_bank_account",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason.strip(),
        before=before,
        after=snapshot(row),
    )
    session.commit()
