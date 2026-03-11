import uuid
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.infrastructure.database import get_session
from src.infrastructure.models.user import User
from src.core.security import decode_access_token
from src.core.exceptions import TokenInvalidError, EmailNotVerifiedError

bearer_scheme = HTTPBearer()


async def get_db() -> AsyncSession:
    async for session in get_session():
        yield session


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> uuid.UUID:
    token = credentials.credentials
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise TokenInvalidError()
    try:
        return uuid.UUID(user_id)
    except ValueError:
        raise TokenInvalidError()


async def get_verified_user_id(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise TokenInvalidError()
    if not user.is_verified:
        raise EmailNotVerifiedError()
    return user_id
