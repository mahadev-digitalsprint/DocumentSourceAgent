"""Pipeline job control: queued (Celery) and direct (sync) execution."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import json
import logging
import os
import uuid
from collections import deque
from typing import Any, Callable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import Company, JobRun, SystemSetting
from app.services.job_run_service import (
    create_job_run,
    get_by_celery_job_id,
    get_by_run_id,
    mark_done,
    mark_failed,
    mark_retrying,
    mark_running,
)
from app.services.run_guard import acquire_singleflight, ensure_no_overlap
from app.services.scheduler_service import scheduler_status, scheduler_tick, update_scheduler_config
from app.utils.time import utc_now_naive

logger = logging.getLogger(__name__)
router = APIRouter()


class JobOut(BaseModel):
    job_id: str
    status: str
    run_id: Optional[str] = None
    result: Optional[dict] = None


class JobRunOut(BaseModel):
    run_id: str
    trigger_type: str
    mode: str
    status: str
    celery_job_id: Optional[str] = None
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    result_payload: Optional[dict] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    items_processed: Optional[int] = None
    error_count: Optional[int] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SchedulerConfigIn(BaseModel):
    enabled: Optional[bool] = None
    poll_seconds: Optional[int] = Field(default=None, ge=5, le=300)
    pipeline_interval_minutes: Optional[int] = Field(default=None, ge=15, le=24 * 60)
    webwatch_interval_minutes: Optional[int] = Field(default=None, ge=5, le=24 * 60)
    digest_hour_utc: Optional[int] = Field(default=None, ge=0, le=23)
    digest_minute_utc: Optional[int] = Field(default=None, ge=0, le=59)


def _get_base_folder(db: Session) -> str:
    setting = db.query(SystemSetting).filter(SystemSetting.key == "base_path").first()
    from app.config import get_settings

    return setting.value if setting else get_settings().base_download_path


def _to_iso(value) -> Optional[str]:
    if not value:
        return None
    try:
        return value.isoformat()
    except Exception:
        return str(value)


def _to_run_out(run: JobRun) -> JobRunOut:
    return JobRunOut(
        run_id=run.run_id,
        trigger_type=run.trigger_type,
        mode=run.mode,
        status=run.status,
        celery_job_id=run.celery_job_id,
        company_id=run.company_id,
        company_name=run.company_name,
        result_payload=run.result_payload or None,
        error_message=run.error_message,
        duration_ms=run.duration_ms,
        items_processed=run.items_processed,
        error_count=run.error_count,
        created_at=_to_iso(run.created_at),
        started_at=_to_iso(run.started_at),
        finished_at=_to_iso(run.finished_at),
        updated_at=_to_iso(run.updated_at),
    )


def _to_run_event_payload(run: JobRun) -> dict:
    return {
        "run_id": run.run_id,
        "trigger_type": run.trigger_type,
        "mode": run.mode,
        "status": run.status,
        "celery_job_id": run.celery_job_id,
        "company_id": run.company_id,
        "company_name": run.company_name,
        "error_message": run.error_message,
        "duration_ms": run.duration_ms,
        "items_processed": run.items_processed,
        "error_count": run.error_count,
        "created_at": _to_iso(run.created_at),
        "started_at": _to_iso(run.started_at),
        "finished_at": _to_iso(run.finished_at),
        "updated_at": _to_iso(run.updated_at),
    }


def _run_version_key(run: JobRun) -> str:
    stamp = run.updated_at or run.finished_at or run.started_at or run.created_at
    stamp_text = _to_iso(stamp) or "na"
    return f"{run.run_id}:{run.status}:{stamp_text}"


def _sync_run_status_from_celery(db: Session, run_id: str, celery_status: str, payload: Any) -> None:
    run = get_by_run_id(db, run_id)
    if not run or run.status in {"DONE", "FAILED"}:
        return

    status = (celery_status or "").upper()
    if status in {"PENDING", "RECEIVED", "STARTED", "PROGRESS"}:
        mark_running(db, run_id)
        return
    if status == "RETRY":
        mark_retrying(db, run_id, "Celery task retrying")
        return
    if status == "SUCCESS":
        mark_done(db, run_id, payload if isinstance(payload, dict) else {"result": str(payload)})
        return
    if status in {"FAILURE", "REVOKED"}:
        mark_failed(db, run_id, str(payload)[:4000])


def _queue_task(
    db: Session,
    *,
    trigger_type: str,
    enqueue: Callable[[str], Any],
    company: Optional[Company] = None,
) -> JobOut:
    run = create_job_run(
        db,
        trigger_type=trigger_type,
        mode="QUEUED",
        status="QUEUED",
        company_id=company.id if company else None,
        company_name=company.company_name if company else None,
    )
    try:
        task = enqueue(run.run_id)
        run.celery_job_id = task.id
        db.commit()
        return JobOut(job_id=task.id, status="QUEUED", run_id=run.run_id)
    except Exception as exc:
        mark_failed(db, run.run_id, str(exc))
        raise HTTPException(
            503,
            f"Celery is unavailable: {exc}. Use a *-direct endpoint instead.",
        ) from exc


def _run_company_sync(company: Company, db: Session) -> dict:
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
        "pdf_sources": {},
        "crawl_errors": [],
        "page_changes": [],
        "has_changes": False,
        "downloaded_docs": [],
        "errors": [],
        "excel_path": None,
        "email_sent": False,
    }

    logger.info("[DIRECT] Pipeline start for %s", company.company_name)
    result = pipeline_graph.invoke(initial_state)
    summary = {
        "company": company.company_name,
        "pdfs_found": len(result.get("pdf_urls", [])),
        "docs_downloaded": len(result.get("downloaded_docs", [])),
        "has_changes": bool(result.get("has_changes")),
        "errors": len(result.get("errors", [])),
        "email_sent": bool(result.get("email_sent")),
    }
    logger.info("[DIRECT] Pipeline finished for %s", company.company_name)
    return summary


@router.post("/run/{company_id}", response_model=JobOut)
def run_pipeline(company_id: int, db: Session = Depends(get_db)):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    from app.tasks import run_pipeline as run_pipeline_task

    with acquire_singleflight("pipeline-launch"):
        ensure_no_overlap(
            db,
            trigger_types=["PIPELINE_ALL"],
            message="Global pipeline run already active. Wait until it completes.",
        )
        ensure_no_overlap(
            db,
            trigger_types=["PIPELINE"],
            company_id=company_id,
            message="Pipeline run for this company is already active.",
        )
        return _queue_task(
            db,
            trigger_type="PIPELINE",
            company=company,
            enqueue=lambda run_id: run_pipeline_task.delay(company_id, run_id),
        )


@router.post("/run-all", response_model=JobOut)
def run_all(db: Session = Depends(get_db)):
    from app.tasks import run_all_companies

    with acquire_singleflight("pipeline-all-launch"):
        ensure_no_overlap(
            db,
            trigger_types=["PIPELINE", "PIPELINE_ALL"],
            message="Pipeline run already active. Wait for current run to finish.",
        )
        return _queue_task(
            db,
            trigger_type="PIPELINE_ALL",
            enqueue=lambda run_id: run_all_companies.delay(run_id),
        )


@router.post("/webwatch-now", response_model=JobOut)
def trigger_webwatch(db: Session = Depends(get_db)):
    from app.tasks import run_hourly_webwatch

    with acquire_singleflight("webwatch-launch"):
        ensure_no_overlap(
            db,
            trigger_types=["WEBWATCH"],
            message="WebWatch run already active. Wait for current run to finish.",
        )
        return _queue_task(
            db,
            trigger_type="WEBWATCH",
            enqueue=lambda run_id: run_hourly_webwatch.delay(run_id),
        )


@router.post("/digest-now", response_model=JobOut)
def trigger_digest(db: Session = Depends(get_db)):
    from app.tasks import run_daily_digest

    with acquire_singleflight("digest-launch"):
        ensure_no_overlap(
            db,
            trigger_types=["DIGEST"],
            message="Digest run already active. Wait for current run to finish.",
        )
    return _queue_task(
        db,
        trigger_type="DIGEST",
        enqueue=lambda run_id: run_daily_digest.delay(run_id),
    )


@router.get("/scheduler/status")
def get_scheduler_status():
    return scheduler_status()


@router.patch("/scheduler/config")
def patch_scheduler_config(body: SchedulerConfigIn):
    payload = body.model_dump(exclude_none=True)
    return update_scheduler_config(payload)


@router.post("/scheduler/tick")
def run_scheduler_tick_now():
    try:
        with acquire_singleflight("scheduler-tick"):
            return scheduler_tick()
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        status = scheduler_status()
        status["busy"] = True
        status["triggers"] = []
        return status


@router.get("/status/{job_id}", response_model=JobOut)
def job_status(job_id: str, db: Session = Depends(get_db)):
    run = get_by_celery_job_id(db, job_id)
    try:
        from app.celery_app import celery_app

        result = celery_app.AsyncResult(job_id)
        payload = result.result if result.ready() else None
        if run:
            _sync_run_status_from_celery(db, run.run_id, result.status, payload)
            run = get_by_run_id(db, run.run_id)
            return JobOut(
                job_id=job_id,
                status=run.status if run else result.status,
                run_id=run.run_id if run else None,
                result=payload if isinstance(payload, dict) else None,
            )
        return JobOut(
            job_id=job_id,
            status=result.status,
            result=payload if isinstance(payload, dict) else None,
        )
    except Exception:
        if run:
            return JobOut(job_id=job_id, status=run.status, run_id=run.run_id, result=run.result_payload)
        return JobOut(job_id=job_id, status="UNKNOWN", result=None)


@router.get("/history", response_model=List[JobRunOut])
def list_job_history(
    limit: int = Query(default=100, ge=1, le=1000),
    status: Optional[str] = Query(default=None),
    trigger_type: Optional[str] = Query(default=None),
    mode: Optional[str] = Query(default=None),
    company_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(JobRun)
    if status:
        query = query.filter(JobRun.status == status.upper())
    if trigger_type:
        query = query.filter(JobRun.trigger_type == trigger_type.upper())
    if mode:
        query = query.filter(JobRun.mode == mode.upper())
    if company_id is not None:
        query = query.filter(JobRun.company_id == company_id)

    items = query.order_by(JobRun.created_at.desc()).limit(limit).all()
    return [_to_run_out(item) for item in items]


@router.get("/history/{run_id}", response_model=JobRunOut)
def get_job_history(run_id: str, db: Session = Depends(get_db)):
    run = get_by_run_id(db, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return _to_run_out(run)


@router.get("/status/run/{run_id}", response_model=JobRunOut)
def job_status_by_run_id(run_id: str, db: Session = Depends(get_db)):
    run = get_by_run_id(db, run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    if run.celery_job_id and run.status not in {"DONE", "FAILED"}:
        try:
            from app.celery_app import celery_app

            result = celery_app.AsyncResult(run.celery_job_id)
            payload = result.result if result.ready() else None
            _sync_run_status_from_celery(db, run.run_id, result.status, payload)
            run = get_by_run_id(db, run_id) or run
        except Exception:
            pass
    return _to_run_out(run)


@router.get("/events")
async def stream_job_events(
    request: Request,
    limit: int = Query(default=30, ge=5, le=200),
    poll_seconds: float = Query(default=2.0, ge=0.5, le=15.0),
    once: bool = Query(default=False),
):
    async def event_stream():
        seen_versions: deque[str] = deque(maxlen=500)
        seen_lookup = set()
        warmup_cutoff = utc_now_naive() - timedelta(minutes=15)

        while True:
            if await request.is_disconnected():
                break

            db = SessionLocal()
            try:
                query = db.query(JobRun)
                query = query.filter(
                    (JobRun.created_at >= warmup_cutoff)
                    | (JobRun.updated_at >= warmup_cutoff)
                )
                runs = query.order_by(JobRun.created_at.desc()).limit(limit).all()
            finally:
                db.close()

            fresh = []
            for run in reversed(runs):
                version = _run_version_key(run)
                if version in seen_lookup:
                    continue
                seen_versions.append(version)
                seen_lookup.add(version)
                fresh.append(run)

            while len(seen_lookup) > seen_versions.maxlen:
                removed = seen_versions.popleft()
                seen_lookup.discard(removed)

            for run in fresh:
                payload = _to_run_event_payload(run)
                yield f"event: job:event\ndata: {json.dumps(payload)}\n\n"

            yield ": ping\n\n"
            if once:
                break
            await asyncio.sleep(poll_seconds)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@router.post("/run-direct/{company_id}", response_model=JobOut)
def run_pipeline_direct(company_id: int, db: Session = Depends(get_db)):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    with acquire_singleflight("pipeline-launch"):
        ensure_no_overlap(
            db,
            trigger_types=["PIPELINE_ALL"],
            message="Global pipeline run already active. Wait until it completes.",
        )
        ensure_no_overlap(
            db,
            trigger_types=["PIPELINE"],
            company_id=company_id,
            message="Pipeline run for this company is already active.",
        )
        run = create_job_run(
            db,
            trigger_type="PIPELINE",
            mode="DIRECT",
            status="RUNNING",
            company_id=company.id,
            company_name=company.company_name,
        )

        try:
            result = _run_company_sync(company, db)
            mark_done(db, run.run_id, result)
            return JobOut(job_id=uuid.uuid4().hex, status="DONE", run_id=run.run_id, result=result)
        except Exception as exc:
            mark_failed(db, run.run_id, str(exc))
            logger.exception("[DIRECT] Pipeline error for %s", company.company_name)
            raise HTTPException(500, str(exc)) from exc


@router.post("/run-all-direct", response_model=JobOut)
def run_all_direct(db: Session = Depends(get_db)):
    with acquire_singleflight("pipeline-all-launch"):
        ensure_no_overlap(
            db,
            trigger_types=["PIPELINE", "PIPELINE_ALL"],
            message="Pipeline run already active. Wait for current run to finish.",
        )
        run = create_job_run(
            db,
            trigger_type="PIPELINE_ALL",
            mode="DIRECT",
            status="RUNNING",
            company_name="ALL_ACTIVE_COMPANIES",
        )

        companies = db.query(Company).filter(Company.active == True).all()
        if not companies:
            payload = {"message": "No active companies found", "total_companies": 0, "succeeded": 0, "failed": 0}
            mark_done(db, run.run_id, payload)
            return JobOut(job_id=uuid.uuid4().hex, status="DONE", run_id=run.run_id, result=payload)

        results = []
        errors = []
        for company in companies:
            try:
                results.append(_run_company_sync(company, db))
            except Exception as exc:
                logger.exception("[DIRECT-ALL] Failed for %s", company.company_name)
                errors.append({"company": company.company_name, "error": str(exc)})

        payload = {
            "total_companies": len(companies),
            "succeeded": len(results),
            "failed": len(errors),
            "companies": results,
            "errors": errors,
        }
        mark_done(db, run.run_id, payload)
        return JobOut(job_id=uuid.uuid4().hex, status="DONE", run_id=run.run_id, result=payload)


@router.post("/webwatch-direct", response_model=JobOut)
def webwatch_direct(db: Session = Depends(get_db)):
    from app.agents.webwatch_agent import webwatch_agent

    with acquire_singleflight("webwatch-launch"):
        ensure_no_overlap(
            db,
            trigger_types=["WEBWATCH"],
            message="WebWatch run already active. Wait for current run to finish.",
        )
        run = create_job_run(
            db,
            trigger_type="WEBWATCH",
            mode="DIRECT",
            status="RUNNING",
            company_name="ALL_ACTIVE_COMPANIES",
        )
        companies = db.query(Company).filter(Company.active == True).all()
        base_folder = _get_base_folder(db)
        results = []
        errors = []
        total_page_changes = 0

        for company in companies:
            state = {
                "company_id": company.id,
                "company_name": company.company_name,
                "company_slug": company.company_slug,
                "website_url": company.website_url,
                "base_folder": base_folder,
            "crawl_depth": company.crawl_depth or 3,
            "pdf_urls": [],
            "pdf_sources": {},
            "page_changes": [],
                "has_changes": False,
                "downloaded_docs": [],
                "errors": [],
                "excel_path": None,
                "email_sent": False,
                "crawl_errors": [],
            }
            try:
                result = webwatch_agent(state)
                change_count = len(result.get("page_changes", []))
                total_page_changes += change_count
                results.append({"company": company.company_name, "page_changes": change_count})
            except Exception as exc:
                errors.append({"company": company.company_name, "error": str(exc)})

        payload = {
            "total_companies": len(companies),
            "total_page_changes": total_page_changes,
            "companies": results,
            "errors": errors,
        }
        mark_done(db, run.run_id, payload)
        return JobOut(job_id=uuid.uuid4().hex, status="DONE", run_id=run.run_id, result=payload)


@router.post("/generate-excel")
def generate_excel_report(company_id: Optional[int] = None, db: Session = Depends(get_db)):
    from app.agents.excel_agent import excel_agent
    from app.workflow.state import PipelineState

    company = None
    if company_id is not None:
        company = db.get(Company, company_id)
        if not company:
            raise HTTPException(404, "Company not found")

    run = create_job_run(
        db,
        trigger_type="EXCEL",
        mode="DIRECT",
        status="RUNNING",
        company_id=company.id if company else None,
        company_name=company.company_name if company else "ALL_COMPANIES",
    )

    try:
        if company:
            state: PipelineState = {
                "company_id": company.id,
                "company_name": company.company_name,
                "company_slug": company.company_slug,
                "website_url": company.website_url,
                "base_folder": _get_base_folder(db),
                "crawl_depth": company.crawl_depth or 3,
                "pdf_urls": [],
                "pdf_sources": {},
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
                "pdf_sources": {},
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

        mark_done(db, run.run_id, {"excel_path": excel_path})
        response = FileResponse(
            excel_path,
            filename=os.path.basename(excel_path),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response.headers["X-Run-Id"] = run.run_id
        return response
    except Exception as exc:
        mark_failed(db, run.run_id, str(exc))
        raise
