"""Job run tracking service for queued/direct operations."""
from __future__ import annotations

from datetime import datetime
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models import JobRun


def create_job_run(
    db: Session,
    *,
    trigger_type: str,
    mode: str,
    status: str = "QUEUED",
    company_id: Optional[int] = None,
    company_name: Optional[str] = None,
    celery_job_id: Optional[str] = None,
) -> JobRun:
    run = JobRun(
        run_id=uuid.uuid4().hex,
        trigger_type=trigger_type,
        mode=mode,
        status=status,
        company_id=company_id,
        company_name=company_name,
        celery_job_id=celery_job_id,
        started_at=datetime.utcnow() if status == "RUNNING" else None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def mark_running(db: Session, run_id: str):
    run = db.query(JobRun).filter(JobRun.run_id == run_id).first()
    if not run:
        return
    run.status = "RUNNING"
    if not run.started_at:
        run.started_at = datetime.utcnow()
    db.commit()


def mark_retrying(db: Session, run_id: str, error_message: str):
    run = db.query(JobRun).filter(JobRun.run_id == run_id).first()
    if not run:
        return
    run.status = "RETRYING"
    run.error_message = (error_message or "")[:4000]
    db.commit()


def mark_done(db: Session, run_id: str, result_payload=None):
    run = db.query(JobRun).filter(JobRun.run_id == run_id).first()
    if not run:
        return
    run.status = "DONE"
    run.result_payload = result_payload or {}
    run.finished_at = datetime.utcnow()
    db.commit()


def mark_failed(db: Session, run_id: str, error_message: str):
    run = db.query(JobRun).filter(JobRun.run_id == run_id).first()
    if not run:
        return
    run.status = "FAILED"
    run.error_message = error_message[:4000]
    run.finished_at = datetime.utcnow()
    db.commit()


def get_by_run_id(db: Session, run_id: str) -> Optional[JobRun]:
    return db.query(JobRun).filter(JobRun.run_id == run_id).first()


def get_by_celery_job_id(db: Session, celery_job_id: str) -> Optional[JobRun]:
    return db.query(JobRun).filter(JobRun.celery_job_id == celery_job_id).first()
