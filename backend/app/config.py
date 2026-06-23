from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./siteshield.db"
    jwt_secret: str = "9c186cadd38b29f09add3609d5da38179f31c9310b78601c2fc48d51f72986d7"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: str = "http://localhost:5173"
    redis_url: str = "redis://localhost:6379/0"
    


settings = Settings()