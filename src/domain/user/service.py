import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from src.infrastructure.models.user import User
from src.infrastructure.models.analysis import Analysis
from src.core.exceptions import NotFoundError
from src.core.logging import get_logger

logger = get_logger(__name__)


async def get_user_profile(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User")
    return user


async def update_user_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str | None,
    image_url: str | None,
) -> User:
    user = await get_user_profile(db, user_id)
    if name is not None:
        user.name = name
    if image_url is not None:
        user.image_url = image_url
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_images(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int,
    limit: int,
) -> tuple[list[Analysis], int]:
    offset = (page - 1) * limit

    count_result = await db.execute(
        select(func.count(Analysis.id)).where(Analysis.user_id == user_id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Analysis)
        .where(Analysis.user_id == user_id)
        .order_by(desc(Analysis.created_at))
        .offset(offset)
        .limit(limit)
    )
    analyses = list(result.scalars().all())
    return analyses, total
