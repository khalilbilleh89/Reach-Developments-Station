"""Project presentation images, scoped to one accessible project."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.modules.audit.service import record_event
from app.modules.projects.models import PROJECT_IMAGE_CATEGORIES, ProjectImage

MAX_IMAGE_BYTES = 10 * 1024 * 1024


def list_images(session: Session, project_id: uuid.UUID) -> list[ProjectImage]:
    return list(
        session.scalars(
            select(ProjectImage)
            .where(ProjectImage.project_id == project_id, ProjectImage.removed_at.is_(None))
            .order_by(ProjectImage.created_at, ProjectImage.id)
        )
    )


def get_image(session: Session, project_id: uuid.UUID, image_id: uuid.UUID) -> ProjectImage:
    image = session.scalar(
        select(ProjectImage).where(
            ProjectImage.project_id == project_id,
            ProjectImage.id == image_id,
            ProjectImage.removed_at.is_(None),
        )
    )
    if image is None:
        raise NotFoundError("Project image not found.")
    return image


def _media_type(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ValidationError("Choose a JPEG, PNG or WebP image.")


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
    safe_name = filename.strip().replace("\\", "/").split("/")[-1][:200]
    if not safe_name:
        raise ValidationError("Image filename is required.")
    image = ProjectImage(
        project_id=project_id,
        category=category,
        filename=safe_name,
        media_type=_media_type(data),
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
        after={"project_id": project_id, "category": category, "filename": safe_name},
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
        before={"project_id": project_id, "category": image.category, "filename": image.filename},
        after={"removed_at": image.removed_at},
    )
    session.commit()
