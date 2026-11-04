"""Authenticated raw uploads, external links and retained marketing library."""

import uuid
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from app.modules.access.dependencies import ActiveActor, DbSession
from app.modules.marketing import assets
from app.modules.marketing.asset_schemas import (
    AssetCreate,
    AssetRead,
    AssetRegister,
    AssetUpdate,
    Kind,
    Placement,
)
from app.modules.marketing.permissions import scope
from app.modules.marketing.schemas import Removal

router = APIRouter()


@router.get("/assets", response_model=AssetRegister)
def list_assets(
    project_id: uuid.UUID,
    session: DbSession,
    actor: ActiveActor,
    placement: Placement = "material",
    search: str = Query("", max_length=160),
    category: str = Query("", max_length=80),
    kind: Kind | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
) -> AssetRegister:
    scope(session, project_id, actor)
    return assets.register(session, project_id, placement, search, category, kind, offset, limit)


@router.post("/assets/links", response_model=AssetRead, status_code=201)
def create_link(
    project_id: uuid.UUID, body: AssetCreate, session: DbSession, actor: ActiveActor
) -> object:
    scope(session, project_id, actor, write=True)
    return assets.create(session, project_id, actor, body)


@router.post("/assets/upload", response_model=AssetRead, status_code=201)
async def upload_asset(
    project_id: uuid.UUID,
    request: Request,
    session: DbSession,
    actor: ActiveActor,
    kind: Kind,
    placement: Placement = "material",
    title: str = Query(min_length=1, max_length=160),
    category: str = Query(min_length=1, max_length=80),
    notes: str = Query("", max_length=500),
    filename: str = Query(min_length=1, max_length=200),
) -> object:
    # Short preflight transaction, then no locks or connections held over upload I/O.
    await run_in_threadpool(assets.authorize_upload, session, project_id, actor)
    from pydantic import ValidationError

    try:
        body = AssetCreate(
            placement=placement, kind=kind, title=title, category=category, notes=notes
        )
    except ValidationError as exc:
        raise HTTPException(422, "Enter valid attachment details; logos must be images.") from exc
    limit = assets.MAX_FILE_BYTES if kind == "video" else assets.MAX_IMAGE_BYTES
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > limit:
            raise HTTPException(413, "File is too large: images/PDFs 10 MB; MP4 videos 50 MB.")
        data.extend(chunk)
    row = await run_in_threadpool(
        assets.create, session, project_id, actor, body, filename, bytes(data)
    )
    return AssetRead.model_validate(row)


@router.put("/assets/{asset_id}", response_model=AssetRead)
def edit_asset(
    project_id: uuid.UUID,
    asset_id: uuid.UUID,
    body: AssetUpdate,
    session: DbSession,
    actor: ActiveActor,
) -> object:
    return assets.change(session, project_id, asset_id, actor, body.expected_version, body)


@router.post("/assets/{asset_id}/delete", status_code=204)
def delete_asset(
    project_id: uuid.UUID,
    asset_id: uuid.UUID,
    body: Removal,
    session: DbSession,
    actor: ActiveActor,
) -> Response:
    assets.change(session, project_id, asset_id, actor, body.expected_version, reason=body.reason)
    return Response(status_code=204)


@router.get("/assets/{asset_id}/file")
def read_file(
    project_id: uuid.UUID,
    asset_id: uuid.UUID,
    request: Request,
    session: DbSession,
    actor: ActiveActor,
    download: bool = False,
) -> Response:
    scope(session, project_id, actor)
    row = assets.get_asset(session, project_id, asset_id, include_data=True)
    if row.data is None:
        raise HTTPException(404, "This material is an external link, not an uploaded file.")
    data = row.data
    disposition = "attachment" if download or row.kind == "document" else "inline"
    headers = {
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(row.filename, safe='')}",
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox",
        "Accept-Ranges": "bytes",
    }
    byte_range = request.headers.get("range")
    if byte_range:
        try:
            unit, span = byte_range.split("=", 1)
            left, right = span.split("-", 1)
            if unit != "bytes" or "," in span or not (left or right):
                raise ValueError
            start = int(left) if left else max(0, len(data) - int(right))
            end = min(int(right), len(data) - 1) if left and right else len(data) - 1
            if start < 0 or start >= len(data) or end < start or (not left and int(right) <= 0):
                raise ValueError
        except ValueError:
            return Response(
                status_code=416, headers={**headers, "Content-Range": f"bytes */{len(data)}"}
            )
        headers["Content-Range"] = f"bytes {start}-{end}/{len(data)}"
        return Response(
            data[start : end + 1], status_code=206, media_type=row.media_type, headers=headers
        )
    return Response(data, media_type=row.media_type, headers=headers)
