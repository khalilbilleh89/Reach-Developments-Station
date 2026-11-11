"""Project-scoped, normalized company logos with retained deletion."""

import hashlib
import io
import uuid

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.projects import company_service
from app.modules.projects.company_models import CompanyLogo

MAX_LOGO_BYTES = 5 * 1024 * 1024


def normalize(data: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(data)) as source:
            if (
                source.format not in {"PNG", "JPEG", "WEBP"}
                or source.width * source.height > 4_000_000
            ):
                raise ValidationError("Choose a PNG, JPEG or WebP logo up to 4 million pixels.")
            source.verify()
        with Image.open(io.BytesIO(data)) as source:
            rendered = ImageOps.exif_transpose(source).convert("RGBA")
            clean = Image.new("RGBA", rendered.size)
            clean.paste(rendered)
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
        raise ValidationError("Choose a valid PNG, JPEG or WebP logo.") from exc
    if len(result) > 16 * 1024 * 1024:
        raise ValidationError("Choose a smaller logo.")
    return result


def get_logo(session: Session, company_id: uuid.UUID, logo_id: uuid.UUID) -> CompanyLogo:
    row = session.scalar(
        select(CompanyLogo).where(
            CompanyLogo.id == logo_id,
            CompanyLogo.company_id == company_id,
            CompanyLogo.is_deleted.is_(False),
        )
    )
    if row is None:
        raise NotFoundError("Company logo not found.")
    return row


def create(
    session: Session, project_id: uuid.UUID, company_id: uuid.UUID, actor: ActorContext, data: bytes
) -> CompanyLogo:
    clean = normalize(data)
    company_service.scope(session, project_id, actor, write=True)
    company_service.company(session, project_id, company_id)
    if session.scalar(
        select(CompanyLogo.id).where(
            CompanyLogo.company_id == company_id, CompanyLogo.is_deleted.is_(False)
        )
    ):
        raise ConflictError("Delete the current logo before uploading a replacement.")
    row = CompanyLogo(company_id=company_id, image=clean, sha256=hashlib.sha256(clean).hexdigest())
    session.add(row)
    session.flush()
    record_event(
        session,
        action="create",
        entity_type="company_logo",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        after={"company_id": company_id, "sha256": row.sha256},
    )
    session.commit()
    return row


def remove(session: Session, row: CompanyLogo, actor: ActorContext, reason: str) -> None:
    if not reason.strip():
        raise ValidationError("Enter a reason for deletion.")
    row.is_deleted = True
    record_event(
        session,
        action="delete",
        entity_type="company_logo",
        entity_id=row.id,
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        reason=reason.strip(),
        before={"company_id": row.company_id, "sha256": row.sha256, "is_deleted": False},
        after={"is_deleted": True},
    )
    session.commit()
