"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = (
        "postgresql://crossword:crosswords_password@localhost:5432/crossword_db"
    )

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_ttl: int = 600  # 10 minutes cache TTL

    # API
    api_title: str = "Crosswords Analytics API"
    api_version: str = "0.1.0"
    api_description: str = "Statistics and analytics service for crosswords application"
    debug: bool = False

    # CORS
    cors_origins: list[str] = [
        "http://localhost",
        "http://localhost:80",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "https://crosswords-mvp-analytics.vercel.app",
    ]


settings = Settings()
