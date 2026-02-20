"""API router — pipeline job control (Celery + direct sync modes)."""
import uuid
import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from app.database import get_db, SessionLocal
from app.models import Company, SystemSetting

logger = logging.getLogger(__name__)
router = APIRouter()


class JobOut(BaseModel):
    job_id: str
    status: str
    result: Optional[dict] = None


# ─────────────────────────────────────────────────────────────────────────────
# Celery-based endpoints (require Redis)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/run/{company_id}", response_model=JobOut)
def run_pipeline(company_id: int):
    try:
        from app.tasks import run_pipeline as _task
        task = _task.delay(company_id)
        return {"job_id": task.id, "status": "QUEUED"}
    except Exception as e:
        raise HTTPException(503, f"Celery not available: {e}. Use /jobs/run-direct/{company_id} instead.")


@router.post("/run-all", response_model=JobOut)
def run_all():
    try:
        from app.tasks import run_all_companies
        task = run_all_companies.delay()
        return {"job_id": task.id, "status": "QUEUED"}
    except Exception as e:
        raise HTTPException(503, f"Celery not available: {e}. Use /jobs/run-all-direct instead.")


@router.get("/status/{job_id}", response_model=JobOut)
def job_status(job_id: str):
    try:
        from app.celery_app import celery_app
        result = celery_app.AsyncResult(job_id)
        return {
            "job_id": job_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
        }
    except Exception:
        return {"job_id": job_id, "status": "UNKNOWN", "result": None}


@router.post("/webwatch-now", response_model=JobOut)
def trigger_webwatch():
    try:
        from app.tasks import run_hourly_webwatch
        task = run_hourly_webwatch.delay()
        return {"job_id": task.id, "status": "QUEUED"}
    except Exception as e:
        raise HTTPException(503, f"Celery not available: {e}. Use /jobs/webwatch-direct instead.")


@router.post("/digest-now", response_model=JobOut)
def trigger_digest():
    try:
        from app.tasks import run_daily_digest
        task = run_daily_digest.delay()
        return {"job_id": task.id, "status": "QUEUED"}
    except Exception as e:
        raise HTTPException(503, f"Celery not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# DIRECT / SYNC endpoints — no Celery required
# ─────────────────────────────────────────────────────────────────────────────

def _get_base_folder(db) -> str:
    s = db.query(SystemSetting).filter(SystemSetting.key == "base_path").first()
    from app.config import get_settings
    return s.value if s else get_settings().base_download_path


def _run_company_sync(company: Company, db) -> dict:
    """Execute full 8-agent pipeline synchronously for one company."""
    from app.workflow.graph import pipeline_graph

    base_folder = _get_base_folder(db)
    initial_state = {
        "company_id": company.id,
        "company_name": company.company_name,
        "company_slug": company.company_slug,
        "website_url": company.website_url,
        "base_folder": base_folder,
        "crawl_depth": company.crawl_depth or 3,
        "pdf_urls": [],
        "crawl_errors": [],
        "page_changes": [],
        "has_changes": False,
        "downloaded_docs": [],
        "errors": [],
        "excel_path": None,
        "email_sent": False,
    }
    logger.info(f"[DIRECT] Pipeline START: {company.company_name}")
    result = pipeline_graph.invoke(initial_state)
    logger.info(
        f"[DIRECT] Pipeline DONE: {company.company_name} | "
        f"PDFs={len(result.get('pdf_urls', []))} | "
        f"Changes={result.get('has_changes')} | Email={result.get('email_sent')}"
    )
    return {
        "company": company.company_name,
        "pdfs_found": len(result.get("pdf_urls", [])),
        "docs_downloaded": len(result.get("downloaded_docs", [])),
        "has_changes": result.get("has_changes", False),
        "errors": len(result.get("errors", [])),
        "email_sent": result.get("email_sent", False),
    }


@router.post("/run-direct/{company_id}")
def run_pipeline_direct(company_id: int, db: Session = Depends(get_db)):
    """
    Run the full pipeline for ONE company synchronously (no Celery/Redis needed).
    NOTE: This is a blocking call — it will run until the pipeline finishes.
    """
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    try:
        result = _run_company_sync(company, db)
        return {"job_id": str(uuid.uuid4()), "status": "DONE", "result": result}
    except Exception as e:
        logger.error(f"[DIRECT] Pipeline error for {company.company_name}: {e}")
        raise HTTPException(500, str(e))


@router.post("/run-all-direct")
def run_all_direct(db: Session = Depends(get_db)):
    """
    Run the full pipeline for ALL active companies synchronously.
    Runs companies sequentially. No Celery/Redis needed.
    """
    companies = db.query(Company).filter(Company.active == True).all()
    if not companies:
        return {"job_id": str(uuid.uuid4()), "status": "DONE",
                "result": {"message": "No active companies found", "total": 0}}

    results = []
    errors = []
    for company in companies:
        try:
            r = _run_company_sync(company, db)
            results.append(r)
        except Exception as e:
            logger.error(f"[DIRECT-ALL] Failed for {company.company_name}: {e}")
            errors.append({"company": company.company_name, "error": str(e)})

    return {
        "job_id": str(uuid.uuid4()),
        "status": "DONE",
        "result": {
            "total_companies": len(companies),
            "succeeded": len(results),
            "failed": len(errors),
            "companies": results,
            "errors": errors,
        }
    }


@router.post("/generate-excel")
def generate_excel_report(company_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Generate an Excel workbook immediately and return it as a file download.
    If company_id is provided, workbook focuses on that company context.
    """
    from app.agents.excel_agent import excel_agent
    from app.workflow.state import PipelineState

    if company_id is not None:
        company = db.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")
        state: PipelineState = {
            "company_id": company.id,
            "company_name": company.company_name,
            "company_slug": company.company_slug,
            "website_url": company.website_url,
            "base_folder": _get_base_folder(db),
            "crawl_depth": company.crawl_depth or 3,
            "pdf_urls": [],
            "crawl_errors": [],
            "page_changes": [],
            "has_changes": False,
            "downloaded_docs": [],
            "errors": [],
            "excel_path": None,
            "email_sent": False,
        }
    else:
        state = {
            "company_id": 0,
            "company_name": "All Companies",
            "company_slug": "all_companies",
            "website_url": "",
            "base_folder": _get_base_folder(db),
            "crawl_depth": 1,
            "pdf_urls": [],
            "crawl_errors": [],
            "page_changes": [],
            "has_changes": False,
            "downloaded_docs": [],
            "errors": [],
            "excel_path": None,
            "email_sent": False,
        }

    result = excel_agent(state)
    excel_path = result.get("excel_path")
    if not excel_path:
        raise HTTPException(500, "Excel generation failed")

    return FileResponse(
        excel_path,
        filename=excel_path.split("/")[-1],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/webwatch-direct")
def webwatch_direct(db: Session = Depends(get_db)):
    """Run WebWatch scan for all active companies directly (no Celery)."""
    from app.agents.webwatch_agent import webwatch_agent
    from app.config import get_settings

    companies = db.query(Company).filter(Company.active == True).all()
    base_folder = _get_base_folder(db)
    results = []
    for c in companies:
        try:
            state = {
                "company_id": c.id, "company_name": c.company_name,
                "company_slug": c.company_slug, "website_url": c.website_url,
                "base_folder": base_folder, "crawl_depth": c.crawl_depth or 3,
                "pdf_urls": [], "page_changes": [], "has_changes": False,
                "downloaded_docs": [], "errors": [], "excel_path": None,
                "email_sent": False, "crawl_errors": [],
            }
            result = webwatch_agent(state)
            changes = result.get("page_changes", [])
            results.append({"company": c.company_name, "page_changes": len(changes)})
        except Exception as e:
            results.append({"company": c.company_name, "error": str(e)})

    return {"status": "DONE", "result": {"companies": results}}
