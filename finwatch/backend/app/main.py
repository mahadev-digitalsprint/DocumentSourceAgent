"""FastAPI application — main entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.database import engine
from app import models
from app.api import companies, jobs, documents, webwatch, alerts, settings as settings_router

# Create all DB tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FinWatch API",
    description="Financial Document Intelligence & Website Monitoring",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(companies.router, prefix="/api/companies", tags=["Companies"])
app.include_router(jobs.router,      prefix="/api/jobs",      tags=["Jobs"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(webwatch.router,  prefix="/api/webwatch",  tags=["WebWatch"])
app.include_router(alerts.router,    prefix="/api/alerts",    tags=["Email Alerts"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "FinWatch API v2"}


@app.get("/api/health")
def health_api():
    return health()


# Backward-compatible aliases used by older frontend pages.
@app.get("/api/metadata/")
@app.get("/api/metadata")
def metadata_alias():
    return RedirectResponse(url="/api/documents/metadata/")


@app.get("/api/changes/document")
def changes_alias():
    return RedirectResponse(url="/api/documents/changes/document")
