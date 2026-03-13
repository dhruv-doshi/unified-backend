import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_db, get_verified_user_id
from src.core.exceptions import success_response
from src.domain.taida import service as taida_service
from src.api.v1.taida.schemas import TaidaAnalyzeRequest, TaidaAnalysisResponse, TaidaResult

router = APIRouter(prefix="/taida", tags=["taida"])


def _to_response(analysis) -> TaidaAnalysisResponse:
    result = None
    if analysis.result_json and analysis.status == "completed":
        try:
            result = TaidaResult(**analysis.result_json)
        except Exception:
            result = None

    return TaidaAnalysisResponse(
        id=analysis.id,
        status=analysis.status,
        request=analysis.request_json,
        result=result,
        created_at=analysis.created_at,
    )


@router.post("/analyze")
async def analyze(
    body: TaidaAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    analysis = await taida_service.run_analysis(
        db,
        user_id=user_id,
        product=body.product,
        target_market=body.target_market,
        sector=body.sector,
        competitors=body.competitors,
    )
    return success_response(_to_response(analysis).model_dump(), "Analysis complete")


@router.get("/analyses")
async def list_analyses(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    analyses = await taida_service.list_analyses(db, user_id)
    return success_response([_to_response(a).model_dump() for a in analyses])


@router.get("/analyses/{analysis_id}")
async def get_analysis(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    analysis = await taida_service.get_analysis(db, analysis_id, user_id)
    return success_response(_to_response(analysis).model_dump())
