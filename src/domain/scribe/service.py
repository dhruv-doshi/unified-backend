import uuid
import json
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from src.core.config import settings
from src.core.logging import get_logger
from src.core.exceptions import NotFoundError, ForbiddenError, AppError
from src.core.transcription import get_transcription_provider
from src.infrastructure.models.scribe import ScribeSession
from src.apps.med_scribe_config import (
    DEFAULT_MODEL,
    SUMMARIZE_SYSTEM_PROMPT,
    GENERATE_NOTES_PROMPTS,
    DIARIZATION_PROMPT,
    SUGGESTIONS_PROMPT,
)

logger = get_logger(__name__)


def _is_valid_audio_format(audio_bytes: bytes) -> bool:
    """Validate audio format by magic bytes (file signature).

    Checks for:
    - WebM: 1A 45 DF A3 (EBML header)
    - WAV: 52 49 46 46 (RIFF header)
    - MP3: FF FB or FF FA or ID3 (MPEG frames or ID3 tags)
    """
    if len(audio_bytes) < 4:
        return False

    # WebM magic bytes
    if audio_bytes[:4] == b"\x1a\x45\xdf\xa3":
        return True

    # WAV magic bytes (RIFF)
    if audio_bytes[:4] == b"RIFF" and len(audio_bytes) > 8 and audio_bytes[8:12] == b"WAVE":
        return True

    # MP3 magic bytes (MPEG frames)
    if audio_bytes[:2] == b"\xff\xfb" or audio_bytes[:2] == b"\xff\xfa":
        return True

    # ID3 tag (MP3)
    if audio_bytes[:3] == b"ID3":
        return True

    return False


async def _call_llm(system_prompt: str, user_content: str) -> dict:
    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{settings.OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)


async def summarize(db: AsyncSession, user_id: uuid.UUID, text: str) -> ScribeSession:
    session = ScribeSession(
        user_id=user_id,
        type="summarize",
        input_text=text,
        status="processing",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    try:
        result = await _call_llm(SUMMARIZE_SYSTEM_PROMPT, f"Text to summarize:\n\n{text}")
        session.result_json = result
        session.status = "completed"
    except Exception as e:
        logger.error("scribe_summarize_failed", session_id=str(session.id), error=str(e))
        session.status = "failed"
        session.error_message = str(e)

    await db.commit()
    await db.refresh(session)
    return session


async def generate_notes(
    db: AsyncSession, user_id: uuid.UUID, text: str, note_type: str
) -> ScribeSession:
    system_prompt = GENERATE_NOTES_PROMPTS.get(note_type, GENERATE_NOTES_PROMPTS["general"])

    session = ScribeSession(
        user_id=user_id,
        type="generate",
        input_text=text,
        status="processing",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    try:
        result = await _call_llm(system_prompt, f"Text to convert to {note_type} notes:\n\n{text}")

        # For clinical notes, generate suggestions
        if note_type == "clinical":
            try:
                suggestions = await _call_llm(
                    SUGGESTIONS_PROMPT,
                    f"Clinical conversation:\n\n{text}",
                )
                result["suggestions"] = suggestions.get("suggestions", [])
            except Exception as e:
                logger.warning(f"Failed to generate suggestions: {str(e)}")
                result["suggestions"] = []
        else:
            result["suggestions"] = []

        session.result_json = result
        session.status = "completed"
    except Exception as e:
        logger.error("scribe_generate_failed", session_id=str(session.id), error=str(e))
        session.status = "failed"
        session.error_message = str(e)

    await db.commit()
    await db.refresh(session)
    return session


async def get_history(db: AsyncSession, user_id: uuid.UUID, limit: int = 20) -> list[ScribeSession]:
    result = await db.execute(
        select(ScribeSession)
        .where(ScribeSession.user_id == user_id)
        .order_by(desc(ScribeSession.created_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_session(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID) -> ScribeSession:
    result = await db.execute(select(ScribeSession).where(ScribeSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundError("ScribeSession")
    if session.user_id != user_id:
        raise ForbiddenError()
    return session


async def transcribe_audio(
    db: AsyncSession, user_id: uuid.UUID, audio_bytes: bytes, content_type: str
) -> dict:
    """Transcribe audio and return speaker-diarized segments."""
    # Validate file size first (before processing)
    max_bytes = settings.TRANSCRIPTION_MAX_FILE_SIZE_MB * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise AppError(
            f"Audio file exceeds {settings.TRANSCRIPTION_MAX_FILE_SIZE_MB} MB",
            "PAYLOAD_TOO_LARGE",
            413,
        )

    # Validate content type and magic bytes
    supported_formats = {"audio/webm", "audio/wav", "audio/mpeg", "audio/mp4"}
    if content_type not in supported_formats:
        raise AppError("Supported formats: WebM, WAV, MP3", "INVALID_AUDIO_FORMAT", 400)

    # Validate magic bytes for audio format (don't trust client Content-Type)
    if not _is_valid_audio_format(audio_bytes):
        raise AppError("Supported formats: WebM, WAV, MP3", "INVALID_AUDIO_FORMAT", 400)

    try:
        # Get transcription provider and transcribe
        provider = get_transcription_provider()
        raw_text = await provider.transcribe(audio_bytes, content_type)

        # Use LLM for speaker diarization
        diarization_result = await _call_llm(DIARIZATION_PROMPT, f"Raw transcript:\n\n{raw_text}")
        segments = diarization_result.get("segments", [])

        # Build full_text from segments
        full_text = " ".join([f"{seg.get('speaker')}: {seg.get('text')}" for seg in segments])

        return {"segments": segments, "full_text": full_text}
    except AppError:
        raise
    except Exception as e:
        logger.error("transcribe_audio_failed", user_id=str(user_id), error=str(e))
        raise AppError(f"Audio transcription failed: {str(e)}", "LLM_PROCESSING_ERROR", 500)


async def transcribe_audio_chunk(
    user_id: uuid.UUID, audio_bytes: bytes, content_type: str
) -> dict:
    """Transcribe a short audio chunk (~10s). Fast path for real-time recording, no LLM diarization."""
    max_bytes = settings.TRANSCRIPTION_MAX_FILE_SIZE_MB * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise AppError(
            f"Audio chunk exceeds {settings.TRANSCRIPTION_MAX_FILE_SIZE_MB} MB",
            "PAYLOAD_TOO_LARGE",
            413,
        )

    supported_formats = {"audio/webm", "audio/wav", "audio/mpeg", "audio/mp4"}
    if content_type not in supported_formats:
        raise AppError("Supported formats: WebM, WAV, MP3", "INVALID_AUDIO_FORMAT", 400)

    if not _is_valid_audio_format(audio_bytes):
        raise AppError("Supported formats: WebM, WAV, MP3", "INVALID_AUDIO_FORMAT", 400)

    try:
        provider = get_transcription_provider()
        text = await provider.transcribe_chunk(audio_bytes, content_type)
        return {"text": text}
    except AppError:
        raise
    except Exception as e:
        logger.error("transcribe_chunk_failed", user_id=str(user_id), error=str(e))
        raise AppError(f"Chunk transcription failed: {str(e)}", "LLM_PROCESSING_ERROR", 500)


async def save_doctor_answers(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    answers: list[dict],
) -> ScribeSession:
    """Save doctor's MCQ answers to a session."""
    session = await get_session(db, session_id, user_id)

    # Validate all suggestion IDs exist in the session's suggestions
    if session.result_json and "suggestions" in session.result_json:
        valid_ids = {s.get("id") for s in session.result_json.get("suggestions", [])}
        for answer in answers:
            if answer.get("suggestion_id") not in valid_ids:
                raise AppError("Suggestion ID not found in session", "INVALID_SUGGESTION_ID", 400)

    # Merge answers into doctor_notes_json
    session.doctor_notes_json = answers
    await db.commit()
    await db.refresh(session)
    return session


async def update_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str | None,
    result_patch: dict | None,
) -> ScribeSession:
    """Update session title and/or result fields."""
    session = await get_session(db, session_id, user_id)

    if title is not None:
        session.title = title

    if result_patch is not None and session.result_json:
        # Deep merge the result_patch into existing result_json
        session.result_json = {**session.result_json, **result_patch}

    await db.commit()
    await db.refresh(session)
    return session


async def delete_session(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Hard delete a session."""
    session = await get_session(db, session_id, user_id)
    await db.delete(session)
    await db.commit()
