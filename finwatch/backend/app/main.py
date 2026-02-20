"""FastAPI main application."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app import models
from app.api import alerts, analytics, companies, crawl, documents, jobs, settings as settings_router, webwatch
from app.config import get_settings
from app.database import SessionLocal, engine
from app.migration import ensure_schema_at_head
from app.schema_compat import ensure_runtime_schema_compatibility
from app.services.scheduler_service import scheduler_loop

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="FinWatch API",
    description="Financial Document Intelligence and Website Monitoring",
    version="2.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(companies.router, prefix="/api/companies", tags=["Companies"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(webwatch.router, prefix="/api/webwatch", tags=["WebWatch"])
app.include_router(crawl.router, prefix="/api/crawl", tags=["Crawl"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Email Alerts"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])


@app.on_event("startup")
def startup_db_migrations():
    if not settings.auto_migrate_on_startup:
        ensure_runtime_schema_compatibility()
    else:
        try:
            ensure_schema_at_head()
        except Exception as exc:
            if settings.migration_strict:
                raise
            logger.warning("[MIGRATION] Failed to run Alembic upgrade (%s). Falling back to create_all.", exc)
            models.Base.metadata.create_all(bind=engine)
        ensure_runtime_schema_compatibility()
    scheduler_loop.start()


@app.on_event("shutdown")
def shutdown_scheduler_loop():
    scheduler_loop.stop()


@app.get("/health")
def health():
    return {"status": "ok", "service": "FinWatch API", "version": "2.2.0"}


@app.get("/ready")
def ready():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    finally:
        db.close()


@app.get("/api/health")
def api_health():
    return health()


@app.get("/api/ready")
def api_ready():
    return ready()


@app.get("/api/metadata/")
@app.get("/api/metadata")
def metadata_alias():
    return RedirectResponse(url="/api/documents/metadata/")


@app.get("/api/changes/document")
def changes_alias():
    return RedirectResponse(url="/api/documents/changes/document")
