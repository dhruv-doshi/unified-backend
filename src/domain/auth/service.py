import secrets
import uuid
from datetime import datetime, timedelta, timezone

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.config import settings
from src.core.security import hash_password, verify_password, create_access_token
from src.core.exceptions import (
    AppError,
    EmailExistsError,
    InvalidCredentialsError,
    EmailNotVerifiedError,
    TokenExpiredError,
    TokenInvalidError,
    NotFoundError,
)
from src.core.email import send_verification_email, send_password_reset_email
from src.core.logging import get_logger
from src.infrastructure.models.user import User
from src.infrastructure.models.auth import EmailVerification, PasswordReset
from src.domain.auth.models import UserPublic, AuthResponse

logger = get_logger(__name__)


def _make_user_public(user: User) -> UserPublic:
    return UserPublic(id=user.id, name=user.name, email=user.email, image=user.image_url)


def _make_token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "email": user.email, "name": user.name})


async def register(db: AsyncSession, name: str, email: str, password: str) -> AuthResponse:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise EmailExistsError()

    user = User(
        name=name,
        email=email,
        hashed_password=hash_password(password),
        is_verified=False,
    )
    db.add(user)
    await db.flush()

    token = secrets.token_urlsafe(32)
    verification = EmailVerification(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(verification)
    await db.commit()
    await db.refresh(user)

    try:
        await send_verification_email(user.email, user.name, token)
    except Exception as e:
        logger.warning("verification_email_failed", user_id=str(user.id), error=str(e))

    access_token = _make_token(user)
    return AuthResponse(accessToken=access_token, user=_make_user_public(user))


async def login(db: AsyncSession, email: str, password: str) -> AuthResponse:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.hashed_password:
        raise InvalidCredentialsError()
    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError()
    if not user.is_verified:
        raise EmailNotVerifiedError()

    return AuthResponse(accessToken=_make_token(user), user=_make_user_public(user))


async def verify_email(db: AsyncSession, token: str) -> None:
    result = await db.execute(select(EmailVerification).where(EmailVerification.token == token))
    verification = result.scalar_one_or_none()
    if not verification:
        raise TokenInvalidError()
    if verification.used_at:
        raise TokenInvalidError()
    if verification.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise TokenExpiredError()

    verification.used_at = datetime.now(timezone.utc)

    result = await db.execute(select(User).where(User.id == verification.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User")
    user.is_verified = True
    await db.commit()


async def forgot_password(db: AsyncSession, email: str) -> None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        return  # Silently succeed to prevent email enumeration

    token = secrets.token_urlsafe(32)
    reset = PasswordReset(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(reset)
    await db.commit()

    try:
        await send_password_reset_email(user.email, user.name, token)
    except Exception as e:
        logger.warning("reset_email_failed", user_id=str(user.id), error=str(e))


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    result = await db.execute(select(PasswordReset).where(PasswordReset.token == token))
    reset = result.scalar_one_or_none()
    if not reset:
        raise TokenInvalidError()
    if reset.used_at:
        raise TokenInvalidError()
    if reset.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise TokenExpiredError()

    result = await db.execute(select(User).where(User.id == reset.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User")

    user.hashed_password = hash_password(new_password)
    reset.used_at = datetime.now(timezone.utc)
    await db.commit()


async def oauth_callback(db: AsyncSession, id_token_str: str, provider: str) -> AuthResponse:
    if provider != "google":
        raise AppError("Unsupported provider", "UNSUPPORTED_PROVIDER", 400)

    try:
        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except Exception:
        raise TokenInvalidError()

    email = idinfo.get("email")
    name = idinfo.get("name", email)
    picture = idinfo.get("picture")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            name=name,
            email=email,
            hashed_password=None,
            image_url=picture,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        if picture and not user.image_url:
            user.image_url = picture
        if not user.is_verified:
            user.is_verified = True
        await db.commit()
        await db.refresh(user)

    return AuthResponse(accessToken=_make_token(user), user=_make_user_public(user))
