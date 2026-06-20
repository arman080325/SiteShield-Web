from datetime import datetime

from pydantic import BaseModel, EmailStr, ConfigDict, field_validator

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
        return v.rstrip("/")
    

class DomainOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    created_at: datetime


class HeaderCheck(BaseModel):
    header: str
    present: bool
    value: str | None = None
    weight: int
    advice: str | None = None


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    domain_id: int
    grade: str
    score: int
    created_at: datetime


class ScanResult(BaseModel):
    scan: ScanOut
    final_url: str | None = None
    status_code: int | None = None
    checks: list[HeaderCheck]
    error: str | None = None