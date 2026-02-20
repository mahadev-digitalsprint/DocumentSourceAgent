"""Job run tracking service for queued/direct operations."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models import JobRun
from app.utils.time import utc_now_naive


def _derive_items_processed(payload) -> int | None:
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("total_companies"), int):
        return int(payload["total_companies"])
    if isinstance(payload.get("companies"), list):
        return len(payload["companies"])
    if isinstance(payload.get("job_ids"), list):
        return len(payload["job_ids"])
    return None


def _derive_error_count(payload) -> int | None:
    if not isinstance(payload, dict):
        return None
    errors = payload.get("errors")
    if isinstance(errors, list):
        return len(errors)
    if isinstance(payload.get("failed"), int):
        return int(payload["failed"])
    return None


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
        started_at=utc_now_naive() if status == "RUNNING" else None,
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
        run.started_at = utc_now_naive()
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
    run.finished_at = utc_now_naive()
    if run.started_at and run.finished_at:
        run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
    run.items_processed = _derive_items_processed(run.result_payload)
    run.error_count = _derive_error_count(run.result_payload)
    db.commit()


def mark_failed(db: Session, run_id: str, error_message: str):
    run = db.query(JobRun).filter(JobRun.run_id == run_id).first()
    if not run:
        return
    run.status = "FAILED"
    run.error_message = error_message[:4000]
    run.finished_at = utc_now_naive()
    if run.started_at and run.finished_at:
        run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
    run.error_count = 1
    db.commit()


def get_by_run_id(db: Session, run_id: str) -> Optional[JobRun]:
    return db.query(JobRun).filter(JobRun.run_id == run_id).first()


def get_by_celery_job_id(db: Session, celery_job_id: str) -> Optional[JobRun]:
    return db.query(JobRun).filter(JobRun.celery_job_id == celery_job_id).first()
