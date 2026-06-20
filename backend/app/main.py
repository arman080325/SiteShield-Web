from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.auth.router import router as auth_router
from app.domains.router import router as domains_router
from app.scanner.router import router as scanner_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SiteShield API")

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