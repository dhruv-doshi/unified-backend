import json
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_db, get_verified_user_id
from src.core.exceptions import success_response
from src.infrastructure.redis import check_daily_limit_ist
from src.domain.analysis import service as analysis_service
from src.domain.analysis.models import LLMAnalysisResult
from src.api.v1.analysis.schemas import AnalysisResponse, UploadResponse, ImprovementShotResponse
from src.apps.registry import AppName
from src.apps.shoot_right_config import IMPROVEMENT_MODEL, DAILY_ANALYSIS_LIMIT, DAILY_IMPROVEMENT_LIMIT
from src.core.llm import LLMClientAsync
from src.workers.analysis_tasks import analyze_image_task

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _to_analysis_response(analysis) -> AnalysisResponse:
    improvement_shot = None
    if analysis.improvement_shot_url:
        improvement_shot = ImprovementShotResponse(
            url=analysis.improvement_shot_url,
            explanation=analysis.improvement_shot_explanation,
            generatedAt=analysis.improvement_shot_at,
        )
    return AnalysisResponse(
        id=analysis.id,
        imageUrl=analysis.original_url,
        thumbnailUrl=analysis.thumbnail_url,
        filename=analysis.filename,
        uploadedAt=analysis.created_at,
        status=analysis.status,
        overallScore=analysis.overall_score,
        summaryHeadline=analysis.summary_headline,
        summaryText=analysis.summary_text,
        metadata=analysis.metadata_,
        histogram=analysis.histogram,
        composition=analysis.composition,
        technical=analysis.technical,
        colorAesthetic=analysis.color_aesthetic,
        clickingTips=analysis.clicking_tips,
        editingTips=analysis.editing_tips,
        improvementShot=improvement_shot,
    )


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_image(
    image: UploadFile = File(...),
    histogram: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    await check_daily_limit_ist(str(user_id), "upload", DAILY_ANALYSIS_LIMIT)

    image_bytes = await image.read()
    client_histogram = json.loads(histogram) if histogram and histogram.strip() else None

    analysis = await analysis_service.create_analysis(
        db=db,
        user_id=user_id,
        filename=image.filename or "upload.jpg",
        image_bytes=image_bytes,
        content_type=image.content_type or "image/jpeg",
        client_histogram=client_histogram,
    )

    # Enqueue Celery task
    analyze_image_task.delay(str(analysis.id))

    return success_response(
        UploadResponse(
            analysisId=analysis.id,
            status="processing",
            message="Upload received. Analysis in progress.",
        ).model_dump(),
        "Upload successful",
        202,
    )


@router.get("/{analysis_id}")
async def get_analysis(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    analysis = await analysis_service.get_analysis(db, analysis_id, user_id)
    return success_response(_to_analysis_response(analysis).model_dump())


@router.post("/{analysis_id}/improvement-shot")
async def improvement_shot(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    llm = LLMClientAsync()

    analysis, is_new = await analysis_service.get_or_create_improvement_shot(
        db, analysis_id, user_id, llm, IMPROVEMENT_MODEL
    )

    if is_new:
        await check_daily_limit_ist(str(user_id), "improvement", DAILY_IMPROVEMENT_LIMIT)

    resp = ImprovementShotResponse(
        url=analysis.improvement_shot_url,
        explanation=analysis.improvement_shot_explanation,
        generatedAt=analysis.improvement_shot_at,
    )
    status_code = 202 if is_new else 200
    return success_response(resp.model_dump(), "Improvement shot ready", status_code)
