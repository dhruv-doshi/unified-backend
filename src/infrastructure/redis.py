import datetime
import zoneinfo
import redis.asyncio as aioredis
from src.core.config import settings
from src.core.exceptions import RateLimitExceededError
from src.core.logging import get_logger

logger = get_logger(__name__)

_redis_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def check_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Increment counter. Raise RateLimitExceededError if over limit."""
    redis = get_redis()
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    if count > limit:
        raise RateLimitExceededError(f"Rate limit exceeded. Max {limit} requests per window.")


async def check_daily_limit_ist(user_id: str, action: str, limit: int) -> None:
    """Rate limit keyed by IST calendar date; TTL expires at next IST midnight."""
    ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    now = datetime.datetime.now(ist)
    date_str = now.strftime("%Y-%m-%d")
    key = f"rate:{user_id}:{action}:daily:{date_str}"

    midnight_ist = (now + datetime.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    ttl = int((midnight_ist - now).total_seconds())

    redis = get_redis()
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, ttl)
    if count > limit:
        raise RateLimitExceededError(f"Daily limit of {limit} reached. Resets at midnight IST.")


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
