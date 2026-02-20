"""API router — pipeline job control."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class JobOut(BaseModel):
    job_id: str
    status: str
    result: Optional[dict] = None


@router.post("/run/{company_id}", response_model=JobOut)
def run_pipeline(company_id: int):
    try:
        from app.tasks import run_pipeline as _task
        task = _task.delay(company_id)
        return {"job_id": task.id, "status": "QUEUED"}
    except Exception as e:
        raise HTTPException(503, f"Celery not available: {e}")


@router.post("/run-all", response_model=JobOut)
def run_all():
    try:
        from app.tasks import run_all_companies
        task = run_all_companies.delay()
        return {"job_id": task.id, "status": "QUEUED"}
    except Exception as e:
        raise HTTPException(503, f"Celery not available: {e}")


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
    except Exception as e:
        return {"job_id": job_id, "status": "UNKNOWN", "result": None}


@router.post("/webwatch-now", response_model=JobOut)
def trigger_webwatch():
    try:
        from app.tasks import run_hourly_webwatch
        task = run_hourly_webwatch.delay()
        return {"job_id": task.id, "status": "QUEUED"}
    except Exception as e:
        raise HTTPException(503, f"Celery not available: {e}")


@router.post("/digest-now", response_model=JobOut)
def trigger_digest():
    try:
        from app.tasks import run_daily_digest
        task = run_daily_digest.delay()
        return {"job_id": task.id, "status": "QUEUED"}
    except Exception as e:
        raise HTTPException(503, f"Celery not available: {e}")


@router.post("/generate-excel")
def generate_excel():
    """Generate Excel for all companies and return download link."""
    try:
        from app.agents.excel_agent import excel_agent
        result = excel_agent({})
        path = result.get("excel_path", "")
        if path:
            import os
            return {"excel_url": f"/api/documents/download-excel", "path": os.path.basename(path)}
        return {"excel_url": None}
    except Exception as e:
        raise HTTPException(500, str(e))
