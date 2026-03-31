import uuid
from fastapi import APIRouter, Depends, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_db, get_verified_user_id
from src.core.exceptions import success_response
from src.domain.scribe import service as scribe_service
from src.api.v1.scribe.schemas import (
    SummarizeRequest,
    GenerateNotesRequest,
    ScribeSessionResponse,
    TranscribeResponse,
    ChunkTranscribeResponse,
    DoctorAnswersRequest,
    UpdateSessionRequest,
)

router = APIRouter(prefix="/scribe", tags=["scribe"])


def _to_response(session) -> ScribeSessionResponse:
    # Convert doctor_notes_json to list of DoctorSuggestionAnswer if present
    doctor_answers = None
    if session.doctor_notes_json:
        from src.api.v1.scribe.schemas import DoctorSuggestionAnswer

        doctor_answers = [DoctorSuggestionAnswer(**ans) for ans in session.doctor_notes_json]

    return ScribeSessionResponse(
        id=session.id,
        type=session.type,
        status=session.status,
        result=session.result_json,
        title=session.title,
        doctor_answers=doctor_answers,
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


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    audio_bytes = await audio.read()
    result = await scribe_service.transcribe_audio(db, user_id, audio_bytes, audio.content_type)
    return success_response(result, "Transcription complete")


@router.post("/transcribe/chunk")
async def transcribe_chunk(
    audio: UploadFile = File(...),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    """Transcribe a short audio chunk (up to ~25s). Fast path for real-time recording, returns raw text only."""
    audio_bytes = await audio.read()
    result = await scribe_service.transcribe_audio_chunk(user_id, audio_bytes, audio.content_type)
    return success_response(result, "Chunk transcribed")


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


@router.post("/{session_id}/doctor-answers")
async def save_doctor_answers(
    session_id: uuid.UUID,
    body: DoctorAnswersRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    session = await scribe_service.save_doctor_answers(
        db, session_id, user_id, [ans.model_dump() for ans in body.answers]
    )
    return success_response(_to_response(session).model_dump(), "Doctor answers saved")


@router.patch("/{session_id}")
async def update_session(
    session_id: uuid.UUID,
    body: UpdateSessionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    session = await scribe_service.update_session(db, session_id, user_id, body.title, body.result)
    return success_response(_to_response(session).model_dump(), "Session updated")


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_verified_user_id),
):
    await scribe_service.delete_session(db, session_id, user_id)
