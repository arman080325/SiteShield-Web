from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.core.ratelimit import custom_rate_limit_exceeded_handler, limiter
from app.auth.router import router as auth_router
from app.domains.router import router as domains_router
from app.scanner.router import router as scanner_router

docs_url = "/docs" if settings.docs_enabled else None
redoc_url = "/redoc" if settings.docs_enabled else None
openapi_url = "/openapi.json" if settings.docs_enabled else None

app = FastAPI(
    title="SiteShield API",
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_exceeded_handler)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )

        # Cache-Control: no-store on sensitive endpoints, auth, pdfs, and errors
        if (
            "Authorization" in request.headers
            or request.url.path.startswith(("/auth", "/domains"))
            or "application/pdf" in content_type
            or response.status_code >= 400
        ):
            response.headers["Cache-Control"] = "no-store"

        return response


app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(domains_router)
app.include_router(scanner_router)


@app.get("/health")
def health():
    return {"status": "ok"}
