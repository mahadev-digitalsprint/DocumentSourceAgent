"""Application settings loaded from environment or .env."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
    azure_openai_deployment: str = "gpt-4.1"
    azure_openai_api_version: str = "2024-12-01-preview"
    openai_api_key: str = ""

    # Crawling
    firecrawl_api_key: str = ""
    tavily_api_key: str = ""
    crawler_mode: str = "auto"  # auto|local|api
    enable_crawl4ai: bool = True
    max_crawl_pages: int = 200

    # Database
    # database_url is preferred for local-first deployments.
    database_url: str = "sqlite:///./finwatch.db"
    # Backward compatibility with existing environments.
    postgres_url: str = ""

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_concurrency: int = 4

    # Google OAuth (optional)
    google_client_id: str = ""
    google_client_secret: str = ""

    # SMTP
    smtp_host: str = "smtp.office365.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    no_reply_mail_password: str = ""
    email_from: str = ""
    email_recipients: str = ""
    sendgrid_api_key: str = ""

    # App
    base_download_path: str = "./downloads"
    webwatch_crawl_depth: int = 3
    auto_migrate_on_startup: bool = True
    migration_strict: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def get_recipients(self) -> List[str]:
        return [email.strip() for email in self.email_recipients.split(",") if email.strip()]

    @property
    def effective_database_url(self) -> str:
        # Prefer explicit DATABASE_URL, otherwise allow legacy POSTGRES_URL.
        return self.database_url or self.postgres_url or "sqlite:///./finwatch.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
