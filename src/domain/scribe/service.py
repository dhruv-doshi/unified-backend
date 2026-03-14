import uuid
import json
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from src.core.config import settings
from src.core.logging import get_logger
from src.core.exceptions import NotFoundError, ForbiddenError
from src.infrastructure.models.scribe import ScribeSession
from src.apps.med_scribe_config import DEFAULT_MODEL, SUMMARIZE_SYSTEM_PROMPT, GENERATE_NOTES_PROMPTS

logger = get_logger(__name__)


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
