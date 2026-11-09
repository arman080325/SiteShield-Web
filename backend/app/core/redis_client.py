import logging
import redis
from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis | None:
    """Return a shared Redis client instance, or None if Redis cannot be reached."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        # Quick ping to verify connectivity
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception as exc:
        logger.warning("Redis is not available: %s", exc)
        return None
