from typing import Optional
from fastapi import APIRouter, Depends, File, Query, UploadFile, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.infrastructure.storage.client import R2StorageClient
from app.modules.auth.models import User
from app.modules.contract_helpers import serialize_media
from app.modules.media.models import Media
from app.modules.media.repository import MediaRepository
from app.modules.media.service import MediaService
from app.shared.auth.dependencies import (
    check_object_lab_access,
    get_user_permitted_lab_ids,
    require_lab_admin,
    verify_user_lab_access,
)

router = APIRouter(prefix="/admin/media", tags=["Media"])


@router.get("")
async def list_media(
    lab_id: Optional[int] = Query(None, description="Filter media by lab ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lab_admin),
):
    """Lists media with strict server-side lab isolation:
    - Super Admin: sees all media, or filtered by lab_id if provided.
    - Lab Admin: sees ONLY media belonging to their permitted labs.
    """
    stmt = select(Media).order_by(Media.id.desc())

    if current_user.is_super_admin:
        if lab_id is not None:
            stmt = stmt.where(Media.lab_id == lab_id)
    else:
        permitted_lab_ids = await get_user_permitted_lab_ids(current_user, db)
        if not permitted_lab_ids:
            return []
        if lab_id is not None:
            if lab_id not in permitted_lab_ids:
                from app.shared.exceptions.custom import ForbiddenException
                raise ForbiddenException("Access denied: You do not have permission to view media for this lab.")
            stmt = stmt.where(Media.lab_id == lab_id)
        else:
            stmt = stmt.where(Media.lab_id.in_(permitted_lab_ids))

    rows = list((await db.execute(stmt)).scalars().all())
    return [serialize_media(row) for row in rows]


MAX_MEDIA_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile = File(...),
    lab_id: Optional[int] = Query(None, description="Lab to assign media to"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lab_admin),
):
    file_bytes = await file.read()
    if len(file_bytes) > MAX_MEDIA_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File size exceeds maximum allowed limit of 10 MB.")

    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml", "application/pdf"}
    content_type = file.content_type or "application/octet-stream"
    if content_type not in allowed_types and not file.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".pdf")):
        raise HTTPException(status_code=400, detail=f"Unsupported media content type: {content_type}")

    # Determine and verify target lab
    target_lab_id: Optional[int] = None
    if current_user.is_super_admin:
        target_lab_id = lab_id
    else:
        permitted = await get_user_permitted_lab_ids(current_user, db)
        if not permitted:
            from app.shared.exceptions.custom import ForbiddenException
            raise ForbiddenException("Access denied: You have no active lab membership.")
        if lab_id is not None:
            if lab_id not in permitted:
                from app.shared.exceptions.custom import ForbiddenException
                raise ForbiddenException("Access denied: You do not have permission for this lab.")
            target_lab_id = lab_id
        elif len(permitted) == 1:
            target_lab_id = permitted[0]
        else:
            raise HTTPException(
                status_code=400,
                detail="User belongs to multiple labs; please provide lab_id query parameter."
            )

    media = await MediaService(MediaRepository(db), R2StorageClient()).upload_media(
        filename=file.filename or "upload.bin",
        content_type=content_type,
        size_bytes=len(file_bytes),
        file_bytes=file_bytes,
        uploaded_by_id=current_user.id,
    )

    if target_lab_id is not None:
        media.lab_id = target_lab_id
        await db.commit()
        await db.refresh(media)

    return serialize_media(media)


@router.delete("/{media_id}")
async def delete_media(
    media_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lab_admin),
):
    repo = MediaRepository(db)
    media = await repo.get_by_id(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    await check_object_lab_access(current_user, media.lab_id, db)
    await MediaService(repo, R2StorageClient()).delete_media(media_id)
    return {"success": True}
