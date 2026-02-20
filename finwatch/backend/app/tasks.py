"""Celery tasks and beat schedule."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from celery.schedules import crontab

from app.celery_app import celery_app
from app.config import get_settings
from app.database import SessionLocal
from app.models import ChangeLog, Company, DocumentRegistry, PageChange, SystemSetting
from app.services.job_run_service import (
    create_job_run,
    mark_done,
    mark_failed,
    mark_retrying,
    mark_running,
)

logger = logging.getLogger(__name__)
settings = get_settings()

celery_app.conf.beat_schedule = {
    "hourly-webwatch": {
        "task": "app.tasks.run_hourly_webwatch",
        "schedule": crontab(minute=0),
    },
    "daily-digest-6am": {
        "task": "app.tasks.run_daily_digest",
        "schedule": crontab(hour=0, minute=30),  # 6:00 AM IST
    },
}


def _get_base_folder(db) -> str:
    setting = db.query(SystemSetting).filter(SystemSetting.key == "base_path").first()
    return setting.value if setting else settings.base_download_path


def _pipeline_initial_state(company: Company, base_folder: str) -> dict:
    return {
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


def _summarize_pipeline_result(company: Company, result: dict) -> dict:
    return {
        "company_id": company.id,
        "company_name": company.company_name,
        "pdfs_found": len(result.get("pdf_urls", [])),
        "docs_downloaded": len(result.get("downloaded_docs", [])),
        "has_changes": bool(result.get("has_changes")),
        "errors": len(result.get("errors", [])),
        "email_sent": bool(result.get("email_sent")),
    }


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="app.tasks.run_pipeline")
def run_pipeline(self, company_id: int, run_id: str | None = None):
    """Run full LangGraph pipeline for one company."""
    db = SessionLocal()
    try:
        if run_id:
            mark_running(db, run_id)

        company = db.get(Company, company_id)
        if not company:
            message = f"Company {company_id} not found"
            if run_id:
                mark_failed(db, run_id, message)
            return {"company_id": company_id, "status": "FAILED", "error": message}

        base_folder = _get_base_folder(db)
        from app.workflow.graph import pipeline_graph

        result = pipeline_graph.invoke(_pipeline_initial_state(company, base_folder))
        payload = _summarize_pipeline_result(company, result)
        if run_id:
            mark_done(db, run_id, payload)
        return payload

    except Exception as exc:
        logger.exception("[TASK] Pipeline failed for company_id=%s", company_id)
        retries = int(getattr(self.request, "retries", 0))
        max_retries = int(self.max_retries or 0)
        if run_id:
            if retries < max_retries:
                mark_retrying(db, run_id, str(exc))
            else:
                mark_failed(db, run_id, str(exc))

        if retries < max_retries:
            raise self.retry(exc=exc)
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.run_all_companies")
def run_all_companies(parent_run_id: str | None = None):
    """Queue pipeline tasks for all active companies."""
    db = SessionLocal()
    try:
        if parent_run_id:
            mark_running(db, parent_run_id)

        companies = db.query(Company).filter(Company.active == True).all()
        if not companies:
            payload = {"total_companies": 0, "queued_jobs": 0, "job_ids": []}
            if parent_run_id:
                mark_done(db, parent_run_id, payload)
            return payload

        job_ids = []
        for company in companies:
            child = create_job_run(
                db,
                trigger_type="PIPELINE",
                mode="QUEUED",
                status="QUEUED",
                company_id=company.id,
                company_name=company.company_name,
            )
            async_result = run_pipeline.delay(company.id, child.run_id)
            child.celery_job_id = async_result.id
            db.commit()
            job_ids.append({"company_id": company.id, "job_id": async_result.id, "run_id": child.run_id})

        payload = {"total_companies": len(companies), "queued_jobs": len(job_ids), "job_ids": job_ids}
        if parent_run_id:
            mark_done(db, parent_run_id, payload)
        return payload
    except Exception as exc:
        if parent_run_id:
            mark_failed(db, parent_run_id, str(exc))
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.run_hourly_webwatch")
def run_hourly_webwatch(run_id: str | None = None):
    """Run WebWatch-only scan for all active companies."""
    db = SessionLocal()
    try:
        if run_id:
            mark_running(db, run_id)

        from app.agents.webwatch_agent import webwatch_agent

        companies = db.query(Company).filter(Company.active == True).all()
        base_folder = _get_base_folder(db)

        summary = []
        total_changes = 0
        for company in companies:
            state = {
                "company_id": company.id,
                "company_name": company.company_name,
                "company_slug": company.company_slug,
                "website_url": company.website_url,
                "base_folder": base_folder,
                "crawl_depth": company.crawl_depth or 3,
                "pdf_urls": [],
                "page_changes": [],
                "has_changes": False,
                "downloaded_docs": [],
                "errors": [],
                "excel_path": None,
                "email_sent": False,
                "crawl_errors": [],
            }
            result = webwatch_agent(state)
            change_count = len(result.get("page_changes", []))
            total_changes += change_count
            summary.append({"company_id": company.id, "company_name": company.company_name, "page_changes": change_count})

        payload = {
            "total_companies": len(companies),
            "total_page_changes": total_changes,
            "companies": summary,
        }
        if run_id:
            mark_done(db, run_id, payload)
        return payload
    except Exception as exc:
        if run_id:
            mark_failed(db, run_id, str(exc))
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.run_daily_digest")
def run_daily_digest(run_id: str | None = None):
    """Aggregate 24h document/page changes and send one digest email."""
    from app.agents.email_agent import _get_recipients, _send_email
    from app.utils.email_template import build_email_html

    db = SessionLocal()
    try:
        if run_id:
            mark_running(db, run_id)

        cutoff = datetime.utcnow() - timedelta(hours=24)
        companies = db.query(Company).filter(Company.active == True).all()
        all_doc_changes = []
        all_page_changes = []
        company_names = []

        for company in companies:
            company_names.append(company.company_name)
            docs = db.query(DocumentRegistry).filter(DocumentRegistry.company_id == company.id).all()
            doc_ids = [doc.id for doc in docs]
            doc_map = {doc.id: doc for doc in docs}

            if doc_ids:
                for change in db.query(ChangeLog).filter(
                    ChangeLog.document_id.in_(doc_ids),
                    ChangeLog.detected_at >= cutoff,
                ).all():
                    doc = doc_map.get(change.document_id)
                    all_doc_changes.append(
                        {
                            "company": company.company_name,
                            "change_type": change.change_type,
                            "url": doc.document_url if doc else "",
                            "doc_type": doc.doc_type if doc else "",
                            "detected_at": str(change.detected_at)[:19],
                        }
                    )

            for page_change in db.query(PageChange).filter(
                PageChange.company_id == company.id,
                PageChange.detected_at >= cutoff,
            ).all():
                all_page_changes.append(
                    {
                        "company": company.company_name,
                        "change_type": page_change.change_type,
                        "page_url": page_change.page_url,
                        "diff_summary": page_change.diff_summary,
                        "detected_at": str(page_change.detected_at)[:19],
                    }
                )

        if not all_doc_changes and not all_page_changes:
            payload = {"sent": False, "reason": "No changes in last 24h"}
            if run_id:
                mark_done(db, run_id, payload)
            return payload

        recipients = _get_recipients(db)
        if not recipients:
            payload = {"sent": False, "reason": "No recipients configured"}
            if run_id:
                mark_done(db, run_id, payload)
            return payload

        html = build_email_html(company_names, all_doc_changes, all_page_changes, datetime.utcnow())
        subject = (
            "FinWatch Daily Digest - "
            f"{len(all_doc_changes)} doc + {len(all_page_changes)} page changes - "
            f"{datetime.utcnow().strftime('%Y-%m-%d')}"
        )
        sent = _send_email(recipients, subject, html, None)
        payload = {
            "sent": bool(sent),
            "recipients": recipients,
            "doc_changes": len(all_doc_changes),
            "page_changes": len(all_page_changes),
        }
        if run_id:
            mark_done(db, run_id, payload)
        return payload
    except Exception as exc:
        if run_id:
            mark_failed(db, run_id, str(exc))
        raise
    finally:
        db.close()
