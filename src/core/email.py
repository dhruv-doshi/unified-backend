from src.core.logging import get_logger

logger = get_logger(__name__)


async def send_verification_email(to: str, name: str, token: str) -> None:
    logger.info("email_skipped", to=to, reason="email_disabled")


async def send_password_reset_email(to: str, name: str, token: str) -> None:
    logger.info("email_skipped", to=to, reason="email_disabled")
