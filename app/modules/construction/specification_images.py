"""Optional specification reference images; all access follows the owning guide."""

import hashlib
import io
import uuid
from datetime import UTC, datetime

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, undefer

from app.core.errors import NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.construction import specifications
from app.modules.construction.models import SpecificationImage
from app.modules.projects.service import lock_project

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_STORED_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 20_000_000
MAX_IMAGES = 20


def normalized_image(data: bytes) -> bytes:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValidationError("Choose an image between 1 byte and 10 MB.")
    try:
        with Image.open(io.BytesIO(data)) as original:
            if original.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValidationError("Choose a JPEG, PNG or WebP image.")
            if original.width * original.height > MAX_PIXELS:
                raise ValidationError("Choose an image no larger than 20 million pixels.")
            original.verify()
        with Image.open(io.BytesIO(data)) as original:
            rendered = ImageOps.exif_transpose(original)
            mode = (
                "RGBA" if "A" in rendered.getbands() or "transparency" in rendered.info else "RGB"
            )
            # Fresh pixels remove uploaded metadata and appended/non-image content.
            clean = Image.new(mode, rendered.size)
            clean.paste(rendered.convert(mode))
            output = io.BytesIO()
            clean.save(output, format="PNG")
            result = output.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValidationError(
            "This image could not be read. Choose a valid JPEG, PNG or WebP."
        ) from exc
    if len(result) > MAX_STORED_BYTES:
        raise ValidationError("This image is too large after processing. Choose a smaller image.")
    return result


def get_image(
    session: Session,
    project_id: uuid.UUID,
    specification_id: uuid.UUID,
    image_id: uuid.UUID,
    actor: ActorContext,
) -> SpecificationImage:
    specifications.authorize(session, project_id, actor)
    specifications._row(session, project_id, specification_id)
    image = session.scalar(
        select(SpecificationImage)
        .where(
            SpecificationImage.id == image_id,
            SpecificationImage.specification_id == specification_id,
            SpecificationImage.removed_at.is_(None),
        )
        .options(undefer(SpecificationImage.image_data))
    )
    if image is None:
        raise NotFoundError("Specification image not found.")
    return image


def add_image(
    session: Session,
    project_id: uuid.UUID,
    specification_id: uuid.UUID,
    actor: ActorContext,
    filename: str,
    data: bytes,
) -> SpecificationImage:
    specifications.authorize(session, project_id, actor, write=True)
    filename = filename.replace("\\", "/").split("/")[-1].strip()[:200]
    if not filename or any(ord(char) < 32 for char in filename):
        raise ValidationError("Choose an image with a valid filename.")
    clean = normalized_image(data)
    lock_project(session, project_id)
    specifications.authorize(session, project_id, actor, write=True)
    specifications._row(session, project_id, specification_id)
    count = session.scalar(
        select(func.count())
        .select_from(SpecificationImage)
        .where(
            SpecificationImage.specification_id == specification_id,
            SpecificationImage.removed_at.is_(None),
        )
    )
    if count >= MAX_IMAGES:
        raise ValidationError(
            "A specification can have up to 20 images. Remove an image before adding another."
        )
    image = SpecificationImage(
        specification_id=specification_id,
        filename=filename,
        image_data=clean,
        sha256=hashlib.sha256(clean).hexdigest(),
        created_by_user_id=actor.user_id,
    )
    session.add(image)
    session.flush()
    record_event(
        session,
        action="specification_image.created",
        entity_type="specification_image",
        entity_id=image.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        after={
            "project_id": project_id,
            "specification_id": specification_id,
            "filename": filename,
            "sha256": image.sha256,
        },
    )
    session.commit()
    session.refresh(image)
    return image


def remove_image(
    session: Session,
    project_id: uuid.UUID,
    specification_id: uuid.UUID,
    image_id: uuid.UUID,
    actor: ActorContext,
    reason: str,
) -> None:
    specifications.authorize(session, project_id, actor, write=True)
    if not reason.strip():
        raise ValidationError("A removal reason is required.")
    lock_project(session, project_id)
    specifications.authorize(session, project_id, actor, write=True)
    image = get_image(session, project_id, specification_id, image_id, actor)
    image.removed_at = datetime.now(UTC)
    record_event(
        session,
        action="specification_image.deleted",
        entity_type="specification_image",
        entity_id=image.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason.strip(),
        before={
            "project_id": project_id,
            "specification_id": specification_id,
            "filename": image.filename,
            "sha256": image.sha256,
        },
        after={"removed_at": image.removed_at},
    )
    session.commit()
