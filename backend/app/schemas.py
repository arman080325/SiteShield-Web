from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.scanner.net.ssrf_guard import UnsafeTargetError, validate_url_syntax


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DomainCreate(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def normalize_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")
        # Prepend scheme if the user omitted it
        if not v.startswith(("http://", "https://")):
            v = "https://" + v
        v = v.rstrip("/")

        # Perform syntax validation only (User Addition 3)
        try:
            validate_url_syntax(v)
        except (UnsafeTargetError, ValueError) as exc:
            raise ValueError(str(exc))

        return v


class DomainOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    created_at: datetime
    monitoring_enabled: bool = False


class MonitoringToggle(BaseModel):
    enabled: bool


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    domain_id: int
    grade: str
    score: int
    created_at: datetime


class ScanDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    domain_id: int
    grade: str
    score: int
    created_at: datetime
    categories: dict | None = None  # parsed from results_json
