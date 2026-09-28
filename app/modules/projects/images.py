"""Project presentation images, scoped to one accessible project."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, undefer

from app.core.errors import NotFoundError, ValidationError
from app.modules.audit.service import record_event
from app.modules.projects.models import PROJECT_IMAGE_CATEGORIES, ProjectImage
from app.modules.projects.service import lock_project

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_FILENAME_LENGTH = 200


def list_images(session: Session, project_id: uuid.UUID) -> list[ProjectImage]:
    """List active metadata; the deferred byte column remains unloaded."""
    return list(
        session.scalars(
            select(ProjectImage)
            .where(ProjectImage.project_id == project_id, ProjectImage.removed_at.is_(None))
            .order_by(ProjectImage.created_at, ProjectImage.id)
        )
    )


def get_image(
    session: Session,
    project_id: uuid.UUID,
    image_id: uuid.UUID,
    *,
    include_data: bool = False,
) -> ProjectImage:
    statement = select(ProjectImage).where(
        ProjectImage.project_id == project_id,
        ProjectImage.id == image_id,
        ProjectImage.removed_at.is_(None),
    )
    if include_data:
        statement = statement.options(undefer(ProjectImage.image_data))
    image = session.scalar(statement)
    if image is None:
        raise NotFoundError("Project image not found.")
    return image


def _media_type(data: bytes) -> str:
    if len(data) >= 4 and data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ValidationError("Choose a JPEG, PNG or WebP image.")


def _safe_filename(filename: str) -> str:
    # Normalize either separator before taking the basename. Strip again after
    # basename extraction so ``folder/   `` cannot create a blank stored name.
    safe_name = filename.replace("\\", "/").split("/")[-1].strip()[:MAX_FILENAME_LENGTH]
    if not safe_name:
        raise ValidationError("Image filename is required.")
    return safe_name


def add_image(
    session: Session,
    *,
    project_id: uuid.UUID,
    category: str,
    filename: str,
    data: bytes,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> ProjectImage:
    if category not in PROJECT_IMAGE_CATEGORIES:
        raise ValidationError("Choose Interior, Exterior or 3D render.")
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValidationError("Image must be between 1 byte and 10 MB.")
    safe_name = _safe_filename(filename)
    media_type = _media_type(data)
    lock_project(session, project_id)
    image = ProjectImage(
        project_id=project_id,
        category=category,
        filename=safe_name,
        media_type=media_type,
        image_data=data,
        created_by_user_id=actor_user_id,
    )
    session.add(image)
    session.flush()
    record_event(
        session,
        action="project_image.created",
        entity_type="project_image",
        entity_id=image.id,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
        after={
            "project_id": project_id,
            "category": category,
            "filename": safe_name,
            "media_type": media_type,
        },
    )
    session.commit()
    session.refresh(image)
    return image


def remove_image(
    session: Session,
    *,
    project_id: uuid.UUID,
    image_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> None:
    lock_project(session, project_id)
    image = get_image(session, project_id, image_id)
    image.removed_at = datetime.now(UTC)
    image.removed_by_user_id = actor_user_id
    record_event(
        session,
        action="project_image.removed",
        entity_type="project_image",
        entity_id=image.id,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
        before={
            "project_id": project_id,
            "category": image.category,
            "filename": image.filename,
            "media_type": image.media_type,
        },
        after={"removed_at": image.removed_at, "removed_by_user_id": actor_user_id},
    )
    session.commit()
