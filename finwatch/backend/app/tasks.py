"""
Celery tasks + periodic scheduler (Celery Beat).

Tasks:
  run_pipeline(company_id)   — Full 8-node LangGraph pipeline for one company
  run_all_companies()        — Trigger pipeline for every active company
  run_daily_digest()         — 24h digest for all companies → single email
  run_hourly_webwatch()      — WebWatch-only pass (no download/extract)

Beat schedule (configured here but activated by passing --beat flag or separate beat service):
  - Every 1 hour  → run_hourly_webwatch
  - Every day 6AM → run_daily_digest
"""
import logging
import os
from celery.schedules import crontab

from app.celery_app import celery_app
from app.config import get_settings
from app.database import SessionLocal
from app.models import Company, SystemSetting

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Celery Beat Schedule ───────────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    "hourly-webwatch": {
        "task": "app.tasks.run_hourly_webwatch",
        "schedule": crontab(minute=0),           # every hour
    },
    "daily-digest-6am": {
        "task": "app.tasks.run_daily_digest",
        "schedule": crontab(hour=0, minute=30),  # 6:00 AM IST = 00:30 UTC
    },
}


def _get_base_folder(db) -> str:
    s = db.query(SystemSetting).filter(SystemSetting.key == "base_path").first()
    return s.value if s else settings.base_download_path


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline task
# ─────────────────────────────────────────────────────────────────────────────
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="app.tasks.run_pipeline")
def run_pipeline(self, company_id: int):
    """Full 8-agent LangGraph pipeline for one company."""
    db = SessionLocal()
    try:
        company = db.query(Company).get(company_id)
        if not company:
            logger.error(f"[TASK] Company {company_id} not found")
            return

        base_folder = _get_base_folder(db)

        from app.workflow.graph import pipeline_graph
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

        logger.info(f"[TASK] Pipeline START: {company.company_name}")
        result = pipeline_graph.invoke(initial_state)
        logger.info(
            f"[TASK] Pipeline DONE: {company.company_name} | "
            f"PDFs={len(result.get('pdf_urls', []))} | "
            f"Changes={result.get('has_changes')} | "
            f"Email={result.get('email_sent')}"
        )

    except Exception as exc:
        logger.error(f"[TASK] Pipeline error company={company_id}: {exc}")
        raise self.retry(exc=exc)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Run all companies
# ─────────────────────────────────────────────────────────────────────────────
@celery_app.task(name="app.tasks.run_all_companies")
def run_all_companies():
    db = SessionLocal()
    try:
        companies = db.query(Company).filter(Company.active == True).all()
        for c in companies:
            run_pipeline.delay(c.id)
        logger.info(f"[TASK] Queued {len(companies)} company pipelines")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Hourly WebWatch only
# ─────────────────────────────────────────────────────────────────────────────
@celery_app.task(name="app.tasks.run_hourly_webwatch")
def run_hourly_webwatch():
    """Lightweight WebWatch-only task — no PDF download."""
    db = SessionLocal()
    try:
        from app.agents.webwatch_agent import webwatch_agent
        base_folder = _get_base_folder(db)
        companies = db.query(Company).filter(Company.active == True).all()
        for c in companies:
            state = {
                "company_id": c.id, "company_name": c.company_name,
                "company_slug": c.company_slug, "website_url": c.website_url,
                "base_folder": base_folder, "crawl_depth": c.crawl_depth or 3,
                "pdf_urls": [], "page_changes": [], "has_changes": False,
                "downloaded_docs": [], "errors": [], "excel_path": None, "email_sent": False,
                "crawl_errors": [],
            }
            result = webwatch_agent(state)
            if result.get("page_changes"):
                logger.info(f"[WEBWATCH] {c.company_name}: {len(result['page_changes'])} changes detected")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Daily digest — multi-company email
# ─────────────────────────────────────────────────────────────────────────────
@celery_app.task(name="app.tasks.run_daily_digest")
def run_daily_digest():
    """Aggregate 24h changes across all companies → one digest email."""
    from datetime import datetime, timedelta
    from app.models import ChangeLog, PageChange, DocumentRegistry, EmailSetting
    from app.utils.email_template import build_email_html
    from app.agents.email_agent import _send_email, _get_recipients, _build_mime

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        companies = db.query(Company).filter(Company.active == True).all()
        all_doc_changes, all_page_changes, company_names = [], [], []

        for c in companies:
            company_names.append(c.company_name)
            docs = db.query(DocumentRegistry).filter(DocumentRegistry.company_id == c.id).all()
            doc_ids = [d.id for d in docs]
            doc_map = {d.id: d for d in docs}

            for ch in db.query(ChangeLog).filter(
                ChangeLog.document_id.in_(doc_ids), ChangeLog.detected_at >= cutoff
            ).all():
                all_doc_changes.append({
                    "company": c.company_name, "change_type": ch.change_type,
                    "url": doc_map[ch.document_id].document_url if ch.document_id in doc_map else "",
                    "doc_type": doc_map[ch.document_id].doc_type if ch.document_id in doc_map else "",
                    "detected_at": str(ch.detected_at)[:19],
                })

            for pc in db.query(PageChange).filter(
                PageChange.company_id == c.id, PageChange.detected_at >= cutoff
            ).all():
                all_page_changes.append({
                    "company": c.company_name, "change_type": pc.change_type,
                    "page_url": pc.page_url, "diff_summary": pc.diff_summary,
                    "detected_at": str(pc.detected_at)[:19],
                })

        if not all_doc_changes and not all_page_changes:
            logger.info("[DIGEST] No changes in last 24h — skipping email")
            return

        recipients = _get_recipients(db)
        if not recipients:
            return

        html = build_email_html(company_names, all_doc_changes, all_page_changes, datetime.utcnow())
        subject = f"FinWatch Daily Digest — {len(all_doc_changes)} doc + {len(all_page_changes)} page changes — {datetime.utcnow().strftime('%Y-%m-%d')}"
        _send_email(recipients, subject, html, None)
        logger.info(f"[DIGEST] Sent to {recipients}")

    finally:
        db.close()
