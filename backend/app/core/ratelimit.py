import os
import sys
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings


def get_user_or_ip(request: Request) -> str:
    """Return user identifier from Bearer token if present, else remote IP address."""
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        return f"user:{token}"
    return get_remote_address(request)


# During pytest, use memory:// storage; otherwise use settings.redis_url with in-memory fallback
_is_testing = os.environ.get("PYTEST_CURRENT_TEST") is not None or "pytest" in sys.modules
storage_uri = "memory://" if _is_testing else settings.redis_url

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=storage_uri,
    in_memory_fallback_enabled=True,
    headers_enabled=True,
)


def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Return JSON 429 response with detail and Retry-After header."""
    response = JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )
    if hasattr(request.state, "view_rate_limit") and request.state.view_rate_limit is not None:
        response = limiter._inject_headers(response, request.state.view_rate_limit)
    else:
        response.headers["Retry-After"] = "60"
    return response
