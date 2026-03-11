import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_db, get_verified_user_id
from src.core.exceptions import success_response
from src.domain.user import service as user_service
from src.domain.analysis import service as analysis_service
from src.core.storage import upload_bytes, make_storage_key
from src.apps.registry import AppName
from src.api.v1.user.schemas import UserProfileResponse, GalleryItem, GalleryResponse

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/profile")
async def get_profile(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    user = await user_service.get_user_profile(db, user_id)
    resp = UserProfileResponse(id=user.id, name=user.name, email=user.email, image=user.image_url)
    return success_response(resp.model_dump())


@router.patch("/profile")
async def update_profile(
    name: str | None = Form(None),
    avatar: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    image_url = None
    if avatar:
        avatar_bytes = await avatar.read()
        key = make_storage_key(AppName.SHOOT_RIGHT, "avatars", str(user_id), "avatar", "jpg")
        image_url = upload_bytes(avatar_bytes, key, avatar.content_type or "image/jpeg")

    user = await user_service.update_user_profile(db, user_id, name, image_url)
    resp = UserProfileResponse(id=user.id, name=user.name, email=user.email, image=user.image_url)
    return success_response(resp.model_dump(), "Profile updated")


@router.get("/images")
async def get_images(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    analyses, total = await user_service.get_user_images(db, user_id, page, limit)
    items = [
        GalleryItem(
            id=a.id,
            url=a.original_url,
            thumbnailUrl=a.thumbnail_url,
            uploadedAt=a.created_at,
            filename=a.filename,
            overallScore=a.overall_score,
            summaryHeadline=a.summary_headline,
            status=a.status,
        )
        for a in analyses
    ]
    resp = GalleryResponse(
        data=items,
        total=total,
        page=page,
        limit=limit,
        hasNext=(page * limit) < total,
    )
    return success_response(resp.model_dump())


@router.delete("/images/{analysis_id}")
async def delete_image(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    await analysis_service.delete_analysis(db, analysis_id, user_id)
    return success_response(None, "Image deleted successfully")
