"""API router — pipeline job control."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class JobStatus(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None


@router.post("/run/{company_id}", response_model=JobStatus)
def run_pipeline(company_id: int):
    from app.tasks import run_pipeline as _task
    task = _task.delay(company_id)
    return {"task_id": task.id, "status": "QUEUED"}


@router.post("/run-all", response_model=JobStatus)
def run_all():
    from app.tasks import run_all_companies
    task = run_all_companies.delay()
    return {"task_id": task.id, "status": "QUEUED"}


@router.get("/status/{task_id}", response_model=JobStatus)
def job_status(task_id: str):
    from app.celery_app import celery_app
    result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }


@router.post("/webwatch-now")
def trigger_webwatch():
    from app.tasks import run_hourly_webwatch
    task = run_hourly_webwatch.delay()
    return {"task_id": task.id, "status": "QUEUED"}


@router.post("/digest-now")
def trigger_digest():
    from app.tasks import run_daily_digest
    task = run_daily_digest.delay()
    return {"task_id": task.id, "status": "QUEUED"}
