"""Scoped marketing media, bounded immutable files and retained removal."""

import hashlib
import io
import uuid
from pathlib import PurePosixPath

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, undefer

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.access.dependencies import ActorContext
from app.modules.audit.service import record_event
from app.modules.marketing.asset_schemas import AssetCreate, AssetRead, AssetRegister, AssetUpdate
from app.modules.marketing.models import MarketingAsset
from app.modules.marketing.permissions import scope

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_PDF_BYTES = 10 * 1024 * 1024


def authorize_upload(session: Session, project_id: uuid.UUID, actor: ActorContext) -> None:
    try:
        scope(session, project_id, actor, write=True)
    finally:
        session.rollback()


def file_payload(kind: str, filename: str, data: bytes) -> tuple[str, str, bytes]:
    name = filename.replace("\\", "/").split("/")[-1].strip()
    if not name or len(name) > 200 or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValidationError("Choose a file with a valid filename up to 200 characters.")
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValidationError("Choose a non-empty file up to 50 MB.")
    suffix = PurePosixPath(name).suffix.lower()
    if kind == "image":
        if suffix not in {".png", ".jpg", ".jpeg"} or len(data) > MAX_IMAGE_BYTES:
            raise ValidationError("Choose a PNG or JPEG image up to 10 MB.")
        try:
            with Image.open(io.BytesIO(data)) as original:
                expected = "PNG" if suffix == ".png" else "JPEG"
                if original.format != expected or original.width * original.height > 20_000_000:
                    raise ValidationError(
                        "Image format must match its extension, up to 20 million pixels."
                    )
                original.verify()
            with Image.open(io.BytesIO(data)) as original:
                rendered = ImageOps.exif_transpose(original)
                mode = (
                    "RGBA"
                    if "A" in rendered.getbands() or "transparency" in rendered.info
                    else "RGB"
                )
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
                "This image could not be decoded. Choose a valid PNG or JPEG."
            ) from exc
        if len(result) > 20 * 1024 * 1024:
            raise ValidationError("Image is too large after processing; choose a smaller image.")
        return str(PurePosixPath(name).with_suffix(".png")), "image/png", result
    if kind == "document":
        if (
            suffix != ".pdf"
            or len(data) > MAX_PDF_BYTES
            or not data.startswith(b"%PDF-")
            or b"%%EOF" not in data[-1024:]
        ):
            raise ValidationError("Choose a PDF document up to 10 MB.")
        return name, "application/pdf", data
    if suffix != ".mp4" or not valid_mp4(data):
        raise ValidationError("Choose an MP4 video up to 50 MB, or save a Drive link.")
    return name, "video/mp4", data


def valid_mp4(data: bytes) -> bool:
    """Bounded ISO base-media container checks; no transcoding or codec claims."""
    offset, boxes = 0, set()
    while offset < len(data):
        if offset + 8 > len(data):
            return False
        size = int.from_bytes(data[offset : offset + 4], "big")
        kind = data[offset + 4 : offset + 8]
        header = 8
        if size == 1:
            if offset + 16 > len(data):
                return False
            size = int.from_bytes(data[offset + 8 : offset + 16], "big")
            header = 16
        elif size == 0:
            size = len(data) - offset
        if size < header or offset + size > len(data):
            return False
        if kind == b"ftyp" and size < header + 8:
            return False
        boxes.add(kind)
        offset += size
    return {b"ftyp", b"moov", b"mdat"} <= boxes


def get_asset(
    session: Session, project_id: uuid.UUID, asset_id: uuid.UUID, *, include_data: bool = False
) -> MarketingAsset:
    query = select(MarketingAsset).where(
        MarketingAsset.project_id == project_id,
        MarketingAsset.id == asset_id,
        MarketingAsset.is_deleted.is_(False),
    )
    if include_data:
        query = query.options(undefer(MarketingAsset.data))
    row = session.scalar(query.execution_options(populate_existing=True))
    if row is None:
        raise NotFoundError("Marketing attachment not found.")
    return row


def register(
    session: Session,
    project_id: uuid.UUID,
    placement: str,
    search: str,
    category: str,
    kind: str | None,
    offset: int,
    limit: int,
) -> AssetRegister:
    base = (
        MarketingAsset.project_id == project_id,
        MarketingAsset.placement == placement,
        MarketingAsset.is_deleted.is_(False),
    )
    filters = list(base)
    if search:
        filters.append(
            or_(
                MarketingAsset.title.icontains(search, autoescape=True),
                MarketingAsset.notes.icontains(search, autoescape=True),
                MarketingAsset.category.icontains(search, autoescape=True),
            )
        )
    if category:
        filters.append(MarketingAsset.category == category)
    if kind:
        filters.append(MarketingAsset.kind == kind)
    total = session.scalar(select(func.count()).select_from(MarketingAsset).where(*filters))
    rows = session.scalars(
        select(MarketingAsset)
        .where(*filters)
        .order_by(MarketingAsset.created_at.desc(), MarketingAsset.id)
        .offset(offset)
        .limit(limit)
    )
    categories = session.scalars(
        select(MarketingAsset.category).where(*base).distinct().order_by(MarketingAsset.category)
    )
    return AssetRegister(
        total=total, items=[AssetRead.model_validate(r) for r in rows], categories=list(categories)
    )


def snapshot(row: MarketingAsset) -> dict:
    return {
        **AssetRead.model_validate(row).model_dump(),
        "project_id": row.project_id,
        "sha256": row.sha256,
        "is_deleted": row.is_deleted,
    }


def commit(
    session: Session,
    row: MarketingAsset,
    actor: ActorContext,
    before: dict | None = None,
    reason: str | None = None,
) -> MarketingAsset:
    session.add(row)
    session.flush()
    record_event(
        session,
        entity_type="marketing_asset",
        entity_id=row.id,
        action="delete" if reason else "update" if before else "create",
        actor_user_id=actor.user_id,
        correlation_id=actor.correlation_id,
        before=before,
        after=snapshot(row),
        reason=reason,
    )
    session.commit()
    return row


def create(
    session: Session,
    project_id: uuid.UUID,
    actor: ActorContext,
    body: AssetCreate,
    filename: str | None = None,
    data: bytes | None = None,
) -> MarketingAsset:
    # Decode before taking the write lock; request already authorized before streaming.
    payload = file_payload(body.kind, filename or "", data) if data is not None else None
    if (payload is None) == (body.external_url is None):
        raise ValidationError("Choose one uploaded file or one external link.")
    scope(session, project_id, actor, write=True)
    count = session.scalar(
        select(func.count())
        .select_from(MarketingAsset)
        .where(
            MarketingAsset.project_id == project_id,
            MarketingAsset.placement == body.placement,
            MarketingAsset.is_deleted.is_(False),
        )
    )
    if count >= (20 if body.placement == "logo" else 500):
        raise ValidationError(
            "Attachment limit reached. Delete an unused item before adding another."
        )
    row = MarketingAsset(project_id=project_id, **body.model_dump())
    if payload:
        row.filename, row.media_type, row.data = payload
        row.byte_count = len(row.data)
        row.sha256 = hashlib.sha256(row.data).hexdigest()
    return commit(session, row, actor)


def change(
    session: Session,
    project_id: uuid.UUID,
    asset_id: uuid.UUID,
    actor: ActorContext,
    expected_version: int,
    body: AssetUpdate | None = None,
    reason: str | None = None,
) -> MarketingAsset:
    scope(session, project_id, actor, write=True)
    row = get_asset(session, project_id, asset_id)
    if row.version != expected_version:
        raise ConflictError("This attachment changed. Reload before trying again.")
    before = snapshot(row)
    if reason is not None:
        row.is_deleted = True
    elif body:
        for key, value in body.model_dump(exclude={"expected_version"}).items():
            setattr(row, key, value)
    row.version += 1
    return commit(session, row, actor, before, reason)
