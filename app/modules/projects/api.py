"""Project workspace routes.

Every route under ``/projects/{project_id}`` resolves the project through
:data:`~app.modules.projects.permissions.AccessibleProject` first, so the
security boundary is established before a handler looks at anything else, and
nested records are always loaded *within* that project.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy import select

from app.modules.access.dependencies import (
    ActiveActor,
    ActorContext,
    DbSession,
    SystemAdmin,
    require_roles,
)
from app.modules.access.models import User
from app.modules.projects import service
from app.modules.projects.models import Project
from app.modules.projects.permissions import (
    AccessibleProject,
    can_view_project_financials,
    require_project_writer,
    require_technical_writer,
    visible_projects,
)
from app.modules.projects.schemas import (
    DocumentReferenceCreateRequest,
    DocumentReferenceRead,
    DocumentReferenceUpdateRequest,
    LandParcelCreateRequest,
    LandParcelRead,
    LandParcelUpdateRequest,
    PermitCreateRequest,
    PermitRead,
    PermitRegister,
    PermitStatusEventRead,
    PermitTransitionRequest,
    PermitTypeCreateRequest,
    PermitTypeRead,
    PermitUpdateRequest,
    PlanningControlRead,
    PlanningControlWriteRequest,
    ProjectAccessRead,
    ProjectAccessUpdateRequest,
    ProjectCreateRequest,
    ProjectDetail,
    ProjectSummary,
    ProjectUpdateRequest,
)
from app.modules.settings.models import CountryPack, Currency

router = APIRouter(prefix="/projects", tags=["projects"])

#: Who may bring a project into existence. Checked before any project exists,
#: so this is a global role gate rather than a membership question.
ProjectCreator = Annotated[ActorContext, Depends(require_roles("system_admin", "project_manager"))]

#: Bound on a page of projects. A register is browsed, not bulk-exported.
_MAX_PAGE = 100


def _currency_code(session: DbSession, currency_id: uuid.UUID | None) -> str | None:
    if currency_id is None:
        return None
    currency = session.get(Currency, currency_id)
    return currency.code if currency is not None else None


def _parcel_read(
    session: DbSession, project: Project, parcel: object, actor: ActorContext
) -> LandParcelRead:
    include = can_view_project_financials(actor)
    return LandParcelRead.build(
        parcel,
        include_financials=include,
        base_currency_code=_currency_code(session, project.base_currency_id) if include else None,
    )


def _permit_read(
    session: DbSession, project: Project, permit: object, actor: ActorContext
) -> PermitRead:
    include = can_view_project_financials(actor)
    return PermitRead.build(
        permit,
        metrics=service.derive_permit_metrics(session, permit),  # type: ignore[arg-type]
        include_financials=include,
        base_currency_code=_currency_code(session, project.base_currency_id) if include else None,
    )


# --------------------------------------------------------------------------- #
# Projects
# --------------------------------------------------------------------------- #


@router.get("", response_model=list[ProjectSummary], summary="List accessible projects")
def list_projects(
    session: DbSession,
    actor: ActiveActor,
    search: Annotated[str | None, Query(max_length=200)] = None,
    project_status: Annotated[str | None, Query(alias="status", max_length=32)] = None,
    country_pack_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=_MAX_PAGE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ProjectSummary]:
    statement = select(Project)
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(Project.name.ilike(pattern) | Project.code.ilike(pattern))
    if project_status:
        statement = statement.where(Project.status == project_status)
    if country_pack_id is not None:
        statement = statement.where(Project.country_pack_id == country_pack_id)

    # The access filter is applied in SQL. Fetching every project and discarding
    # the inaccessible ones afterwards would put them in memory and one refactor
    # away from the response body.
    statement = visible_projects(statement, actor=actor)
    projects = list(session.scalars(statement.order_by(Project.code).limit(limit).offset(offset)))

    ids = [project.id for project in projects]
    permits = service.permit_summary(session, ids)
    parcels = service.parcel_counts(session, ids)
    summaries = []
    for project in projects:
        summary = ProjectSummary.model_validate(project)
        summary.parcel_count = parcels.get(project.id, 0)
        for key, value in permits.get(project.id, {}).items():
            setattr(summary, key, value)
        summaries.append(summary)
    return summaries


@router.post(
    "",
    response_model=ProjectDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
def create_project(
    payload: ProjectCreateRequest,
    session: DbSession,
    actor: ProjectCreator,
) -> ProjectDetail:
    project = service.create_project(
        session,
        actor_user_id=actor.user_id,
        actor_is_system_admin=actor.is_system_admin,
        correlation_id=actor.correlation_id,
        **payload.model_dump(),
    )
    return _project_detail(session, project)


def _project_detail(session: DbSession, project: Project) -> ProjectDetail:
    detail = ProjectDetail.model_validate(project)
    counts = service.permit_summary(session, [project.id]).get(project.id, {})
    for key, value in counts.items():
        setattr(detail, key, value)
    detail.parcel_count = service.parcel_counts(session, [project.id]).get(project.id, 0)

    pack = session.get(CountryPack, project.country_pack_id)
    detail.country_code = pack.country_code if pack is not None else None
    detail.base_currency_code = _currency_code(session, project.base_currency_id)
    detail.reporting_currency_code = _currency_code(session, project.reporting_currency_id)
    if project.project_manager_user_id is not None:
        manager = session.get(User, project.project_manager_user_id)
        detail.project_manager_display_name = manager.display_name if manager else None
    if project.planned_start is not None and project.planned_completion is not None:
        detail.planned_duration_days = (project.planned_completion - project.planned_start).days
    return detail


@router.get("/{project_id}", response_model=ProjectDetail, summary="Read a project")
def read_project(project: AccessibleProject, session: DbSession) -> ProjectDetail:
    return _project_detail(session, project)


@router.patch("/{project_id}", response_model=ProjectDetail, summary="Update a project")
def update_project(
    payload: ProjectUpdateRequest,
    project: AccessibleProject,
    session: DbSession,
    actor: ActiveActor,
) -> ProjectDetail:
    require_project_writer(actor)
    updated = service.update_project(
        session,
        project=project,
        actor_user_id=actor.user_id,
        actor_is_system_admin=actor.is_system_admin,
        correlation_id=actor.correlation_id,
        **payload.model_dump(exclude_unset=True),
    )
    return _project_detail(session, updated)


# --------------------------------------------------------------------------- #
# Project access — System Administrator only
# --------------------------------------------------------------------------- #


def _access_read(session: DbSession, access: object) -> ProjectAccessRead:
    user = session.get(User, access.user_id)  # type: ignore[attr-defined]
    return ProjectAccessRead(
        id=access.id,  # type: ignore[attr-defined]
        project_id=access.project_id,  # type: ignore[attr-defined]
        user_id=access.user_id,  # type: ignore[attr-defined]
        email=user.email if user else "",
        display_name=user.display_name if user else "",
        role_keys=sorted(user.role_keys) if user else [],
        is_active=access.is_active,  # type: ignore[attr-defined]
        phase_scope=access.phase_scope,  # type: ignore[attr-defined]
        granted_at=access.granted_at,  # type: ignore[attr-defined]
        revoked_at=access.revoked_at,  # type: ignore[attr-defined]
    )


@router.get(
    "/{project_id}/access",
    response_model=list[ProjectAccessRead],
    summary="List project access",
)
def list_project_access(
    project: AccessibleProject, session: DbSession, _actor: SystemAdmin
) -> list[ProjectAccessRead]:
    return [
        _access_read(session, access)
        for access in service.list_project_access(session, project_id=project.id)
    ]


@router.put(
    "/{project_id}/access/{user_id}",
    response_model=ProjectAccessRead,
    summary="Grant or restore project access",
)
def grant_project_access(
    user_id: Annotated[uuid.UUID, Path()],
    project: AccessibleProject,
    session: DbSession,
    actor: SystemAdmin,
) -> ProjectAccessRead:
    access = service.grant_project_access(
        session,
        project_id=project.id,
        user_id=user_id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
    )
    return _access_read(session, access)


@router.patch(
    "/{project_id}/access/{user_id}",
    response_model=ProjectAccessRead,
    summary="Revoke or restore project access",
)
def update_project_access(
    user_id: Annotated[uuid.UUID, Path()],
    payload: ProjectAccessUpdateRequest,
    project: AccessibleProject,
    session: DbSession,
    actor: SystemAdmin,
) -> ProjectAccessRead:
    if payload.is_active:
        access = service.grant_project_access(
            session,
            project_id=project.id,
            user_id=user_id,
            actor_user_id=actor.user_id,
            correlation_id=actor.correlation_id,
        )
    else:
        access = service.revoke_project_access(
            session,
            project=project,
            user_id=user_id,
            actor_user_id=actor.user_id,
            correlation_id=actor.correlation_id,
        )
    return _access_read(session, access)


# --------------------------------------------------------------------------- #
# Land parcels
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/parcels", response_model=list[LandParcelRead], summary="List land parcels"
)
def list_parcels(
    project: AccessibleProject, session: DbSession, actor: ActiveActor
) -> list[LandParcelRead]:
    return [
        _parcel_read(session, project, parcel, actor)
        for parcel in service.list_parcels(session, project_id=project.id)
    ]


@router.post(
    "/{project_id}/parcels",
    response_model=LandParcelRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a land parcel",
)
def create_parcel(
    payload: LandParcelCreateRequest,
    project: AccessibleProject,
    session: DbSession,
    actor: ActiveActor,
) -> LandParcelRead:
    require_project_writer(actor)
    parcel = service.create_parcel(
        session,
        project=project,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **payload.model_dump(),
    )
    return _parcel_read(session, project, parcel, actor)


@router.get(
    "/{project_id}/parcels/{parcel_id}",
    response_model=LandParcelRead,
    summary="Read a land parcel",
)
def read_parcel(
    parcel_id: Annotated[uuid.UUID, Path()],
    project: AccessibleProject,
    session: DbSession,
    actor: ActiveActor,
) -> LandParcelRead:
    parcel = service.get_parcel(session, project_id=project.id, parcel_id=parcel_id)
    return _parcel_read(session, project, parcel, actor)


@router.patch(
    "/{project_id}/parcels/{parcel_id}",
    response_model=LandParcelRead,
    summary="Update a land parcel",
)
def update_parcel(
    parcel_id: Annotated[uuid.UUID, Path()],
    payload: LandParcelUpdateRequest,
    project: AccessibleProject,
    session: DbSession,
    actor: ActiveActor,
) -> LandParcelRead:
    require_project_writer(actor)
    parcel = service.get_parcel(session, project_id=project.id, parcel_id=parcel_id)
    updated = service.update_parcel(
        session,
        project=project,
        parcel=parcel,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **payload.model_dump(exclude_unset=True),
    )
    return _parcel_read(session, project, updated, actor)


# --------------------------------------------------------------------------- #
# Planning controls
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/parcels/{parcel_id}/planning-controls",
    response_model=PlanningControlRead,
    summary="Read planning controls",
)
def read_planning_controls(
    parcel_id: Annotated[uuid.UUID, Path()],
    project: AccessibleProject,
    session: DbSession,
    _actor: ActiveActor,
) -> PlanningControlRead:
    service.get_parcel(session, project_id=project.id, parcel_id=parcel_id)
    control = service.get_planning_control(session, project_id=project.id, parcel_id=parcel_id)
    return PlanningControlRead.model_validate(control)


@router.put(
    "/{project_id}/parcels/{parcel_id}/planning-controls",
    response_model=PlanningControlRead,
    summary="Record the current planning controls",
)
def write_planning_controls(
    parcel_id: Annotated[uuid.UUID, Path()],
    payload: PlanningControlWriteRequest,
    project: AccessibleProject,
    session: DbSession,
    actor: ActiveActor,
) -> PlanningControlRead:
    require_technical_writer(actor)
    parcel = service.get_parcel(session, project_id=project.id, parcel_id=parcel_id)
    control = service.write_planning_control(
        session,
        project=project,
        parcel=parcel,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        values=payload.model_dump(),
    )
    return PlanningControlRead.model_validate(control)


# --------------------------------------------------------------------------- #
# Permit types
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/permit-types",
    response_model=list[PermitTypeRead],
    summary="Permit types available to this project",
)
def list_permit_types(
    project: AccessibleProject, session: DbSession, _actor: ActiveActor
) -> list[PermitTypeRead]:
    return [
        PermitTypeRead.model_validate(value)
        for value in service.list_permit_types(session, project=project)
    ]


@router.post(
    "/{project_id}/permit-types",
    response_model=PermitTypeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a permit type to this project's jurisdiction",
)
def create_permit_type(
    payload: PermitTypeCreateRequest,
    project: AccessibleProject,
    session: DbSession,
    actor: ActiveActor,
) -> PermitTypeRead:
    """Extend the permit vocabulary without leaving the permit workspace.

    Gated on the technical writer, which is the role already trusted with
    permits and planning controls — not on the System Administrator that the
    generic Settings write requires. A project team can add the consent their
    authority asks for; they still cannot touch tax rules or global
    configuration, because this route can only ever write one category into one
    country pack.
    """
    require_technical_writer(actor)
    value = service.create_permit_type(
        session,
        project=project,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **payload.model_dump(),
    )
    return PermitTypeRead.model_validate(value)


# --------------------------------------------------------------------------- #
# Permits
# --------------------------------------------------------------------------- #


@router.get("/{project_id}/permits", response_model=PermitRegister, summary="Permit register")
def list_permits(
    project: AccessibleProject,
    session: DbSession,
    actor: ActiveActor,
    permit_status: Annotated[str | None, Query(alias="status", max_length=32)] = None,
    permit_type_code: Annotated[str | None, Query(max_length=64)] = None,
    parcel_id: Annotated[uuid.UUID | None, Query()] = None,
    is_blocking: Annotated[bool | None, Query()] = None,
    is_critical_path: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PermitRegister:
    permits = service.list_permits(
        session,
        project_id=project.id,
        status=permit_status,
        permit_type_code=permit_type_code,
        parcel_id=parcel_id,
        is_blocking=is_blocking,
        is_critical_path=is_critical_path,
        limit=limit,
        offset=offset,
    )
    totals = service.permit_register_totals(
        session,
        project_id=project.id,
        status=permit_status,
        permit_type_code=permit_type_code,
        parcel_id=parcel_id,
        is_blocking=is_blocking,
        is_critical_path=is_critical_path,
    )
    # The counts describe every permit matching the filter; `permits` is the
    # requested page of them.
    return PermitRegister(
        permits=[_permit_read(session, project, permit, actor) for permit in permits],
        **totals,
    )


@router.post(
    "/{project_id}/permits",
    response_model=PermitRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a permit",
)
def create_permit(
    payload: PermitCreateRequest,
    project: AccessibleProject,
    session: DbSession,
    actor: ActiveActor,
) -> PermitRead:
    require_technical_writer(actor)
    permit = service.create_permit(
        session,
        project=project,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **payload.model_dump(),
    )
    return _permit_read(session, project, permit, actor)


@router.get("/{project_id}/permits/{permit_id}", response_model=PermitRead, summary="Read a permit")
def read_permit(
    permit_id: Annotated[uuid.UUID, Path()],
    project: AccessibleProject,
    session: DbSession,
    actor: ActiveActor,
) -> PermitRead:
    permit = service.get_permit(session, project_id=project.id, permit_id=permit_id)
    return _permit_read(session, project, permit, actor)


@router.patch(
    "/{project_id}/permits/{permit_id}", response_model=PermitRead, summary="Update a permit"
)
def update_permit(
    permit_id: Annotated[uuid.UUID, Path()],
    payload: PermitUpdateRequest,
    project: AccessibleProject,
    session: DbSession,
    actor: ActiveActor,
) -> PermitRead:
    require_technical_writer(actor)
    permit = service.get_permit(session, project_id=project.id, permit_id=permit_id)
    updated = service.update_permit(
        session,
        project=project,
        permit=permit,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **payload.model_dump(exclude_unset=True),
    )
    return _permit_read(session, project, updated, actor)


@router.post(
    "/{project_id}/permits/{permit_id}/transitions",
    response_model=PermitRead,
    status_code=status.HTTP_201_CREATED,
    summary="Move a permit to a new status",
)
def transition_permit(
    permit_id: Annotated[uuid.UUID, Path()],
    payload: PermitTransitionRequest,
    project: AccessibleProject,
    session: DbSession,
    actor: ActiveActor,
) -> PermitRead:
    require_technical_writer(actor)
    permit = service.get_permit(session, project_id=project.id, permit_id=permit_id)
    updated = service.transition_permit(
        session,
        permit=permit,
        to_status=payload.to_status,
        effective_date=payload.effective_date,
        reason=payload.reason,
        notes=payload.notes,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
    )
    return _permit_read(session, project, updated, actor)


@router.get(
    "/{project_id}/permits/{permit_id}/status-history",
    response_model=list[PermitStatusEventRead],
    summary="Read a permit's status history",
)
def read_status_history(
    permit_id: Annotated[uuid.UUID, Path()],
    project: AccessibleProject,
    session: DbSession,
    _actor: ActiveActor,
) -> list[PermitStatusEventRead]:
    service.get_permit(session, project_id=project.id, permit_id=permit_id)
    return [
        PermitStatusEventRead.model_validate(event)
        for event in service.list_status_history(session, permit_id=permit_id)
    ]


# --------------------------------------------------------------------------- #
# Document references
# --------------------------------------------------------------------------- #


@router.get(
    "/{project_id}/documents",
    response_model=list[DocumentReferenceRead],
    summary="List document references",
)
def list_documents(
    project: AccessibleProject,
    session: DbSession,
    _actor: ActiveActor,
    parcel_id: Annotated[uuid.UUID | None, Query()] = None,
    permit_id: Annotated[uuid.UUID | None, Query()] = None,
    document_type_code: Annotated[str | None, Query(max_length=64)] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> list[DocumentReferenceRead]:
    return [
        DocumentReferenceRead.model_validate(document)
        for document in service.list_documents(
            session,
            project_id=project.id,
            parcel_id=parcel_id,
            permit_id=permit_id,
            document_type_code=document_type_code,
            is_active=is_active,
        )
    ]


@router.post(
    "/{project_id}/documents",
    response_model=DocumentReferenceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a document reference",
)
def create_document(
    payload: DocumentReferenceCreateRequest,
    project: AccessibleProject,
    session: DbSession,
    actor: ActiveActor,
) -> DocumentReferenceRead:
    require_technical_writer(actor)
    values = payload.model_dump()
    document = service.create_document(
        session,
        project=project,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **{**values, "external_url": str(payload.external_url)},
    )
    return DocumentReferenceRead.model_validate(document)


@router.patch(
    "/{project_id}/documents/{document_id}",
    response_model=DocumentReferenceRead,
    summary="Update a document reference",
)
def update_document(
    document_id: Annotated[uuid.UUID, Path()],
    payload: DocumentReferenceUpdateRequest,
    project: AccessibleProject,
    session: DbSession,
    actor: ActiveActor,
) -> DocumentReferenceRead:
    require_technical_writer(actor)
    document = service.get_document(session, project_id=project.id, document_id=document_id)
    changes = payload.model_dump(exclude_unset=True)
    if "external_url" in changes and changes["external_url"] is not None:
        changes["external_url"] = str(changes["external_url"])
    updated = service.update_document(
        session,
        project=project,
        document=document,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        **changes,
    )
    return DocumentReferenceRead.model_validate(updated)
