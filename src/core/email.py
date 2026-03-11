import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


async def _send_email(to: str, subject: str, html_body: str) -> None:
    message = MIMEMultipart("alternative")
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USERNAME}>"
    message["To"] = to
    message["Subject"] = subject
    message.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info("email_sent", to=to, subject=subject)
    except Exception as e:
        logger.error("email_send_failed", to=to, error=str(e))
        raise


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
