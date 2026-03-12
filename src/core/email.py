import httpx
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


async def _send_email(to: str, subject: str, html_body: str) -> None:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"Shoot Right <{settings.RESEND_FROM_EMAIL}>",
                    "to": [to],
                    "subject": subject,
                    "html": html_body,
                },
            )
            response.raise_for_status()
        logger.info("email_sent", to=to, subject=subject)
    except Exception as e:
        logger.error("email_send_failed", to=to, error=str(e))
        # email is non-fatal — app continues without it


async def send_verification_email(to: str, name: str, token: str) -> None:
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    html = f"""
    <h2>Welcome to Shoot Right, {name}!</h2>
    <p>Please verify your email address by clicking the link below:</p>
    <a href="{verify_url}" style="background:#6366f1;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;">
        Verify Email
    </a>
    <p>This link expires in 24 hours.</p>
    <p>If you didn't create an account, please ignore this email.</p>
    """
    await _send_email(to, "Verify your Shoot Right account", html)


async def send_password_reset_email(to: str, name: str, token: str) -> None:
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    html = f"""
    <h2>Password Reset Request</h2>
    <p>Hi {name}, we received a request to reset your password.</p>
    <a href="{reset_url}" style="background:#6366f1;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;">
        Reset Password
    </a>
    <p>This link expires in 1 hour. If you didn't request a password reset, please ignore this email.</p>
    """
    await _send_email(to, "Reset your Shoot Right password", html)
