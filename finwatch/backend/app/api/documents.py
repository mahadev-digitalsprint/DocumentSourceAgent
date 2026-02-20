"""API router — documents, metadata, change logs, Excel download."""
import os
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import json
from pydantic import BaseModel
from sqlalchemy import case, func

from app.database import get_db
from app.models import DocumentRegistry, MetadataRecord, ChangeLog, ErrorLog, Company, IngestionRetry
from app.utils.time import utc_now_naive

router = APIRouter()


class ReviewUpdateIn(BaseModel):
    needs_review: bool = False


class RetryUpdateIn(BaseModel):
    status: str
    next_retry_in_minutes: Optional[int] = None
    reason_code: Optional[str] = None
    last_error: Optional[str] = None


def _api_error(status_code: int, code: str, message: str, details: Optional[dict] = None):
    raise HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "details": details or {},
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Documents
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/")
def list_documents(
    company_id: Optional[int] = None,
    doc_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    q = db.query(DocumentRegistry)
    if company_id:
        q = q.filter(DocumentRegistry.company_id == company_id)
    if doc_type:
        q = q.filter(DocumentRegistry.doc_type.like(f"%{doc_type}%"))
    if status:
        q = q.filter(DocumentRegistry.status == status)
    docs = q.order_by(DocumentRegistry.created_at.desc()).limit(limit).all()
    return [
        {
            "id": d.id,
            "company_id": d.company_id,
            "document_url": d.document_url,    # consistent naming — was "url"
            "doc_type": d.doc_type,
            "status": d.status,
            "file_size_bytes": d.file_size_bytes,
            "file_size_kb": round(d.file_size_bytes / 1024, 1) if d.file_size_bytes else None,
            "page_count": d.page_count,
            "is_scanned": d.is_scanned,
            "language": d.language,
            "metadata_extracted": d.metadata_extracted,
            "classifier_confidence": d.classifier_confidence,
            "classifier_version": d.classifier_version,
            "needs_review": d.needs_review,
            "source_type": d.source_type,
            "source_domain": d.source_domain,
            "discovery_strategy": d.discovery_strategy,
            "first_seen_at": str(d.first_seen_at or ""),
            "last_seen_at": str(d.last_seen_at or ""),
            "local_path": d.local_path,
            "last_checked": str(d.last_checked or ""),
            "created_at": str(d.created_at or ""),
        }
        for d in docs
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Metadata — list ALL metadata records (used by Metadata page)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/metadata/")
@router.get("/metadata")
def list_all_metadata(
    company_id: Optional[int] = None,
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    """Return all metadata records joined with company name."""
    q = (
        db.query(MetadataRecord, DocumentRegistry, Company)
        .join(DocumentRegistry, MetadataRecord.document_id == DocumentRegistry.id)
        .join(Company, DocumentRegistry.company_id == Company.id)
    )
    if company_id:
        q = q.filter(DocumentRegistry.company_id == company_id)

    results = q.order_by(MetadataRecord.created_at.desc()).limit(limit).all()
    return [
        {
            "id": m.id,
            "document_id": m.document_id,
            "company_name": c.company_name,
            "company_id": c.id,
            "document_url": d.document_url,
            "document_category": (d.doc_type or "").split("|")[0],
            "document_type": m.document_type or (d.doc_type or "").split("|")[-1],
            "headline": m.headline,
            "filing_date": m.filing_date,
            "period_end_date": m.period_end_date,
            "language": m.language,
            "audit_flag": m.audit_flag,
            "audit_status": "Audited" if m.audit_flag else "Unaudited",
            "preliminary_document": m.preliminary_document,
            "income_statement": m.income_statement,
            "note_flag": m.note_flag,
            "filing_data_source": m.filing_data_source,
            "raw_llm_response": m.raw_llm_response if isinstance(m.raw_llm_response, dict) else {},
            "created_at": str(m.created_at or ""),
        }
        for m, d, c in results
    ]


@router.get("/{doc_id}/metadata")
def get_single_metadata(doc_id: int, db: Session = Depends(get_db)):
    m = db.query(MetadataRecord).filter(MetadataRecord.document_id == doc_id).first()
    if not m:
        raise HTTPException(404, "No metadata for this document")
    return {
        "id": m.id, "document_id": doc_id,
        "headline": m.headline, "filing_date": m.filing_date,
        "filing_data_source": m.filing_data_source, "language": m.language,
        "period_end_date": m.period_end_date, "document_type": m.document_type,
        "income_statement": m.income_statement, "preliminary_document": m.preliminary_document,
        "note_flag": m.note_flag, "audit_flag": m.audit_flag,
        "raw_llm_response": m.raw_llm_response if isinstance(m.raw_llm_response, dict) else {},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Document Changes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/changes/")
@router.get("/changes/document")   # alias for frontend compatibility
def get_change_logs(
    company_id: Optional[int] = None,
    hours: int = 24,
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = (
        db.query(ChangeLog, DocumentRegistry, Company)
        .join(DocumentRegistry, ChangeLog.document_id == DocumentRegistry.id)
        .join(Company, DocumentRegistry.company_id == Company.id)
        .filter(ChangeLog.detected_at >= cutoff)
    )
    if company_id:
        q = q.filter(DocumentRegistry.company_id == company_id)
    changes = q.order_by(ChangeLog.detected_at.desc()).limit(limit).all()
    return [
        {
            "id": c.id,
            "document_id": c.document_id,
            "company_name": co.company_name,
            "company_id": co.id,
            "doc_type": d.doc_type,
            "document_url": d.document_url,
            "change_type": c.change_type,
            "old_hash": c.old_hash,
            "new_hash": c.new_hash,
            "detected_at": str(c.detected_at),
        }
        for c, d, co in changes
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/errors/")
def get_error_logs(
    company_id: Optional[int] = None,
    limit: int = Query(default=200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    q = db.query(ErrorLog)
    if company_id:
        q = q.filter(ErrorLog.company_id == company_id)
    return [
        {
            "id": e.id, "step": e.step, "error_type": e.error_type,
            "company_id": e.company_id,
            "document_url": e.document_url, "error_message": e.error_message,
            "created_at": str(e.created_at),
        }
        for e in q.order_by(ErrorLog.created_at.desc()).limit(limit).all()
    ]


@router.get("/sources/summary")
def source_summary(
    company_id: Optional[int] = None,
    hours: int = Query(default=168, ge=1, le=24 * 365),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    cutoff = utc_now_naive() - timedelta(hours=hours)
    q = db.query(
        func.coalesce(DocumentRegistry.source_domain, "UNKNOWN").label("source_domain"),
        func.coalesce(DocumentRegistry.discovery_strategy, "UNKNOWN").label("discovery_strategy"),
        func.coalesce(DocumentRegistry.source_type, "UNKNOWN").label("source_type"),
        func.count(DocumentRegistry.id).label("documents_total"),
        func.count(func.distinct(DocumentRegistry.company_id)).label("companies_count"),
        func.sum(case((DocumentRegistry.created_at >= cutoff, 1), else_=0)).label("new_docs_window"),
        func.sum(case((DocumentRegistry.needs_review == True, 1), else_=0)).label("needs_review_count"),
        func.max(DocumentRegistry.last_seen_at).label("last_seen_at"),
    )
    if company_id:
        q = q.filter(DocumentRegistry.company_id == company_id)
    rows = (
        q.group_by(
            func.coalesce(DocumentRegistry.source_domain, "UNKNOWN"),
            func.coalesce(DocumentRegistry.discovery_strategy, "UNKNOWN"),
            func.coalesce(DocumentRegistry.source_type, "UNKNOWN"),
        )
        .order_by(func.count(DocumentRegistry.id).desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "source_domain": row[0],
            "discovery_strategy": row[1],
            "source_type": row[2],
            "documents_total": int(row[3] or 0),
            "companies_count": int(row[4] or 0),
            "new_docs_window": int(row[5] or 0),
            "needs_review_count": int(row[6] or 0),
            "last_seen_at": str(row[7] or ""),
        }
        for row in rows
    ]


@router.get("/retries")
def list_ingestion_retries(
    status: Optional[str] = Query(default=None),
    company_id: Optional[int] = None,
    source_domain: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    q = db.query(IngestionRetry)
    if status:
        q = q.filter(IngestionRetry.status == status.upper())
    if company_id:
        q = q.filter(IngestionRetry.company_id == company_id)
    if source_domain:
        q = q.filter(func.lower(IngestionRetry.source_domain) == source_domain.lower())
    rows = q.order_by(IngestionRetry.created_at.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "company_id": row.company_id,
            "document_url": row.document_url,
            "source_domain": row.source_domain,
            "reason_code": row.reason_code,
            "failure_count": row.failure_count,
            "next_retry_at": str(row.next_retry_at or ""),
            "status": row.status,
            "last_error": row.last_error,
            "last_attempt_at": str(row.last_attempt_at or ""),
            "created_at": str(row.created_at or ""),
            "updated_at": str(row.updated_at or ""),
        }
        for row in rows
    ]


@router.patch("/retries/{retry_id}")
def update_ingestion_retry(retry_id: int, body: RetryUpdateIn, db: Session = Depends(get_db)):
    retry = db.get(IngestionRetry, retry_id)
    if not retry:
        _api_error(404, "RETRY_NOT_FOUND", "Retry entry not found", {"retry_id": retry_id})

    next_status = (body.status or "").upper()
    allowed = {"PENDING", "DEAD", "RESOLVED"}
    if next_status not in allowed:
        _api_error(400, "INVALID_RETRY_STATUS", "Unsupported retry status", {"status": body.status, "allowed": sorted(allowed)})

    retry.status = next_status
    if body.reason_code:
        retry.reason_code = body.reason_code[:100]
    if body.last_error:
        retry.last_error = body.last_error[:2000]

    now = utc_now_naive()
    retry.last_attempt_at = now
    if next_status == "PENDING":
        delay = int(body.next_retry_in_minutes or 0)
        retry.next_retry_at = now + timedelta(minutes=max(0, min(delay, 24 * 60)))
    else:
        retry.next_retry_at = None
    db.commit()
    db.refresh(retry)
    return {
        "id": retry.id,
        "status": retry.status,
        "next_retry_at": str(retry.next_retry_at or ""),
        "failure_count": retry.failure_count,
        "reason_code": retry.reason_code,
    }


@router.get("/review/queue")
def review_queue(
    company_id: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    q = db.query(DocumentRegistry).filter(DocumentRegistry.needs_review == True)
    if company_id:
        q = q.filter(DocumentRegistry.company_id == company_id)
    docs = q.order_by(DocumentRegistry.created_at.desc()).limit(limit).all()
    return [
        {
            "id": d.id,
            "company_id": d.company_id,
            "document_url": d.document_url,
            "doc_type": d.doc_type,
            "status": d.status,
            "classifier_confidence": d.classifier_confidence,
            "classifier_version": d.classifier_version,
            "needs_review": d.needs_review,
            "created_at": str(d.created_at or ""),
        }
        for d in docs
    ]


@router.patch("/review/{doc_id}")
def update_review_flag(doc_id: int, body: ReviewUpdateIn, db: Session = Depends(get_db)):
    doc = db.get(DocumentRegistry, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    doc.needs_review = body.needs_review
    db.commit()
    return {
        "id": doc.id,
        "needs_review": doc.needs_review,
        "classifier_confidence": doc.classifier_confidence,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Excel download
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{company_id}/excel")
def download_excel(company_id: int, db: Session = Depends(get_db)):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    from app.agents.excel_agent import excel_agent
    from app.workflow.state import PipelineState
    state: PipelineState = {"company_id": company_id, "company_name": company.company_name,
                             "website_url": company.website_url, "downloaded_docs": []}
    result = excel_agent(state)
    path = result.get("excel_path", "")
    if not path or not os.path.exists(path):
        raise HTTPException(500, "Excel generation failed")
    return FileResponse(path, filename=os.path.basename(path),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
