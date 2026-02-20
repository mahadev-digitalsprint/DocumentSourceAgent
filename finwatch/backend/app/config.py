"""
Centralised settings — all secrets come from environment variables / .env file.
No credentials are hardcoded here. Copy backend/.env.example to backend/.env
and fill in your real values.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # ── LLM ───────────────────────────────────────────────────────────────────
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
    azure_openai_deployment: str = "gpt-4.1"
    azure_openai_api_version: str = "2024-12-01-preview"
    openai_api_key: str = ""

    # ── Crawling ──────────────────────────────────────────────────────────────
    firecrawl_api_key: str = ""
    tavily_api_key: str = ""

    # ── Azure PostgreSQL ──────────────────────────────────────────────────────
    postgres_url: str = "postgresql://user:password@localhost:5432/finwatch?sslmode=require"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── Google OAuth2 (read from env only — never hardcode) ───────────────────
    google_client_id: str = ""
    google_client_secret: str = ""

    # ── SMTP (Office365) ──────────────────────────────────────────────────────
    smtp_host: str = "smtp.office365.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    no_reply_mail_password: str = ""
    email_from: str = ""
    email_recipients: str = ""

    # ── SendGrid (optional) ───────────────────────────────────────────────────
    sendgrid_api_key: str = ""

    # ── App ───────────────────────────────────────────────────────────────────
    base_download_path: str = "/app/downloads"
    celery_concurrency: int = 4
    webwatch_crawl_depth: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def get_recipients(self) -> List[str]:
        return [e.strip() for e in self.email_recipients.split(",") if e.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
