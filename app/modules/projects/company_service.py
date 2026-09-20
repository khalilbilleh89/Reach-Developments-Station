"""Project-scoped company commands with serialized writes and retained removal."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects.company_models import CompanyBankAccount, ProjectCompany
from app.modules.projects.company_schemas import BankAccountRead, CompanyDetail
from app.modules.projects.models import Project
from app.modules.projects.permissions import FINANCIAL_ROLES, whole_project_ids

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


def detail(session: Session, row: ProjectCompany) -> CompanyDetail:
    accounts = session.scalars(
        select(CompanyBankAccount)
        .where(
            CompanyBankAccount.company_id == row.id,
            CompanyBankAccount.is_deleted.is_(False),
        )
        .order_by(CompanyBankAccount.created_at, CompanyBankAccount.id)
    ).all()
    return CompanyDetail(
        **{key: getattr(row, key) for key in CompanyDetail.model_fields if key != "bank_accounts"},
        bank_accounts=[BankAccountRead.model_validate(item) for item in accounts],
    )


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
    for key, value in values.items():
        setattr(row, key, value.strip() or None if isinstance(value, str) else value)
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
