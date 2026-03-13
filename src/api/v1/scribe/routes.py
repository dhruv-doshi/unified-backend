import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_db, get_verified_user_id
from src.core.exceptions import success_response
from src.domain.scribe import service as scribe_service
from src.api.v1.scribe.schemas import SummarizeRequest, GenerateNotesRequest, ScribeSessionResponse

router = APIRouter(prefix="/scribe", tags=["scribe"])


def _to_response(session) -> ScribeSessionResponse:
    return ScribeSessionResponse(
        id=session.id,
        type=session.type,
        status=session.status,
        result=session.result_json,
        created_at=session.created_at,
    )


@router.post("/summarize")
async def summarize(
    body: SummarizeRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    session = await scribe_service.summarize(db, user_id, body.text)
    return success_response(_to_response(session).model_dump(), "Summarization complete")


@router.post("/generate")
async def generate_notes(
    body: GenerateNotesRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    session = await scribe_service.generate_notes(db, user_id, body.text, body.note_type)
    return success_response(_to_response(session).model_dump(), "Notes generated")


@router.get("/history")
async def get_history(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    sessions = await scribe_service.get_history(db, user_id)
    return success_response([_to_response(s).model_dump() for s in sessions])


@router.get("/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    session = await scribe_service.get_session(db, session_id, user_id)
    return success_response(_to_response(session).model_dump())
