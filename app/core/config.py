"""
Application configuration settings
"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import validator
import json


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "RMS Billing Software"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # API
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5173"]
    
    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 0

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Trial Settings
    TRIAL_DAYS: int = 14
    TRIAL_REMINDER_DAYS: List[int] = [7, 12, 13]
    
    @validator("TRIAL_REMINDER_DAYS", pre=True)
    def assemble_reminder_days(cls, v):
        if isinstance(v, str):
            return [int(i.strip()) for i in v.split(",")]
        return v

    # Subscription Limits
    FREE_TIER_INVOICE_LIMIT: int = 10
    FREE_TIER_CUSTOMER_LIMIT: int = 50
    FREE_TIER_USER_LIMIT: int = 1

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: str = "RMS Billing"

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [i.strip() for i in v.split(",")]
        return v

    @validator("TRIAL_REMINDER_DAYS", pre=True)
    def parse_trial_reminder_days(cls, v):
        if isinstance(v, str):
            return [int(i.strip()) for i in v.split(",")]
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
