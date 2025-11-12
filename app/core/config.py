"""
Application configuration
Loads settings from environment variables
"""
from pydantic_settings import BaseSettings
from typing import Optional, List
from pydantic import field_validator


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "RMS Billing API"
    APP_VERSION: str = "1.0.0"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # API
    API_V1_PREFIX: str = "/api/v1"
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 0

    # Email (SMTP) - Optional for development
    MAIL_USERNAME: Optional[str] = None
    MAIL_PASSWORD: Optional[str] = None
    MAIL_FROM: Optional[str] = None
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # CORS Origins
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # File uploads
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024
    UPLOAD_DIR: str = "uploads"

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Trial
    TRIAL_DAYS: int = 14

    # Free tier
    FREE_TIER_INVOICE_LIMIT: int = 10
    FREE_TIER_CUSTOMER_LIMIT: int = 50
    FREE_TIER_USER_LIMIT: int = 1

    @field_validator("CORS_ORIGINS", mode="before")
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


# Create settings instance
settings = Settings()