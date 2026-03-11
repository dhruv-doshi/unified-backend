import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.exceptions import NotFoundError, ForbiddenError, AppError
from src.core.logging import get_logger
from src.core.storage import upload_bytes, delete_object, make_storage_key
from src.infrastructure.models.analysis import Analysis
from src.domain.analysis.image_utils import validate_image, extract_exif, compute_histogram, create_thumbnail
from src.apps.registry import AppName

logger = get_logger(__name__)


async def create_analysis(
    db: AsyncSession,
    user_id: uuid.UUID,
    filename: str,
    image_bytes: bytes,
    content_type: str,
    client_histogram: dict | None,
) -> Analysis:
    validate_image(image_bytes, content_type)

    file_id = str(uuid.uuid4())
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    app_name = AppName.SHOOT_RIGHT

    # Upload original
    original_key = make_storage_key(app_name, "originals", str(user_id), file_id, ext)
    original_url = upload_bytes(image_bytes, original_key, content_type)

    # Create thumbnail
    thumbnail_bytes = create_thumbnail(image_bytes)
    thumbnail_key = make_storage_key(app_name, "thumbnails", str(user_id), file_id, "jpg")
    thumbnail_url = upload_bytes(thumbnail_bytes, thumbnail_key, "image/jpeg")

    # Extract metadata
    exif_data = extract_exif(image_bytes)

    # Use client histogram if provided, else compute server-side
    histogram = client_histogram if client_histogram else compute_histogram(image_bytes)

    analysis = Analysis(
        user_id=user_id,
        app_name=app_name,
        filename=filename,
        original_url=original_url,
        thumbnail_url=thumbnail_url,
        status="processing",
        metadata_=exif_data,
        histogram=histogram,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis


async def get_analysis(db: AsyncSession, analysis_id: uuid.UUID, user_id: uuid.UUID) -> Analysis:
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise NotFoundError("Analysis")
    if analysis.user_id != user_id:
        raise ForbiddenError()
    return analysis


async def update_analysis_completed(
    db: AsyncSession,
    analysis_id: uuid.UUID,
    llm_result: dict,
) -> None:
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if not analysis:
        return

    analysis.status = "completed"
    analysis.overall_score = llm_result.get("overall_score")
    analysis.summary_headline = llm_result.get("summary_headline")
    analysis.summary_text = llm_result.get("summary_text")
    analysis.composition = llm_result.get("composition")
    analysis.technical = llm_result.get("technical")
    analysis.color_aesthetic = llm_result.get("color_aesthetic")
    analysis.clicking_tips = llm_result.get("clicking_tips")
    analysis.editing_tips = llm_result.get("editing_tips")
    await db.commit()


async def update_analysis_failed(db: AsyncSession, analysis_id: uuid.UUID, error: str) -> None:
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if not analysis:
        return
    analysis.status = "failed"
    analysis.error_message = error
    await db.commit()


async def get_or_create_improvement_shot(
    db: AsyncSession,
    analysis_id: uuid.UUID,
    user_id: uuid.UUID,
    llm_client,
    model: str,
) -> tuple[Analysis, bool]:
    """Returns (analysis, is_new). If already generated, return existing."""
    analysis = await get_analysis(db, analysis_id, user_id)

    if analysis.status != "completed":
        raise AppError("Analysis must be completed before generating improvement shot", "ANALYSIS_NOT_COMPLETE", 400)

    if analysis.improvement_shot_explanation:
        return analysis, False

    # Generate prescription
    analysis_data = {
        "overall_score": analysis.overall_score,
        "summary_text": analysis.summary_text,
        "composition": analysis.composition,
        "technical": analysis.technical,
        "color_aesthetic": analysis.color_aesthetic,
        "clicking_tips": analysis.clicking_tips,
    }
    explanation = await llm_client.generate_improvement_prescription(analysis_data, model)
    analysis.improvement_shot_explanation = explanation
    analysis.improvement_shot_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(analysis)
    return analysis, True


async def delete_analysis(db: AsyncSession, analysis_id: uuid.UUID, user_id: uuid.UUID) -> None:
    analysis = await get_analysis(db, analysis_id, user_id)

    # Delete from storage
    try:
        app_name = analysis.app_name
        file_id = str(analysis.id)
        ext = analysis.filename.rsplit(".", 1)[-1].lower() if "." in analysis.filename else "jpg"
        delete_object(make_storage_key(app_name, "originals", str(user_id), file_id, ext))
        delete_object(make_storage_key(app_name, "thumbnails", str(user_id), file_id, "jpg"))
    except Exception as e:
        logger.warning("storage_delete_failed", analysis_id=str(analysis_id), error=str(e))

    await db.delete(analysis)
    await db.commit()
