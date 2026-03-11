from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_db
from src.core.exceptions import success_response
from src.domain.auth import service as auth_service
from src.api.v1.auth.schemas import (
    RegisterRequest,
    LoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    OAuthCallbackRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await auth_service.register(db, body.name, body.email, body.password)
    return success_response(result.model_dump(), "Registration successful", 201)


@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await auth_service.login(db, body.email, body.password)
    return success_response(result.model_dump(), "Login successful")


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.forgot_password(db, body.email)
    return success_response(None, "If the email exists, a reset link has been sent")


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.reset_password(db, body.token, body.password)
    return success_response(None, "Password reset successful")


@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.verify_email(db, body.token)
    return success_response(None, "Email verified successfully")


@router.post("/oauth-callback")
async def oauth_callback(body: OAuthCallbackRequest, db: AsyncSession = Depends(get_db)):
    result = await auth_service.oauth_callback(db, body.idToken, body.provider)
    return success_response(result.model_dump(), "OAuth login successful")
