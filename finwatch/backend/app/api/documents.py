"""API router — documents, metadata, change logs, Excel download."""
import os
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import DocumentRegistry, MetadataRecord, ChangeLog, ErrorLog

router = APIRouter()


@router.get("/")
def list_documents(
    company_id: Optional[int] = None,
    doc_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(DocumentRegistry)
    if company_id:
        q = q.filter(DocumentRegistry.company_id == company_id)
    if doc_type:
        q = q.filter(DocumentRegistry.doc_type == doc_type)
    if status:
        q = q.filter(DocumentRegistry.status == status)
    docs = q.order_by(DocumentRegistry.created_at.desc()).all()
    return [
        {
            "id": d.id, "url": d.document_url,
            "doc_type": d.doc_type, "status": d.status,
            "file_size_kb": round(d.file_size_bytes / 1024, 1) if d.file_size_bytes else None,
            "page_count": d.page_count, "is_scanned": d.is_scanned,
            "language": d.language, "metadata_extracted": d.metadata_extracted,
            "local_path": d.local_path, "last_checked": str(d.last_checked or ""),
        }
        for d in docs
    ]


@router.get("/{doc_id}/metadata")
def get_metadata(doc_id: int, db: Session = Depends(get_db)):
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
    }


@router.get("/{company_id}/excel")
def download_excel(company_id: int, db: Session = Depends(get_db)):
    from app.models import Company
    from app.agents.excel_agent import _build_excel
    from app.config import get_settings

    company = db.query(Company).get(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    settings = get_settings()
    path = _build_excel(db, company, settings.base_download_path)
    return FileResponse(path, filename=os.path.basename(path),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.get("/changes/")
def get_change_logs(
    company_id: Optional[int] = None,
    hours: int = 24,
    db: Session = Depends(get_db),
):
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    docs = db.query(DocumentRegistry)
    if company_id:
        docs = docs.filter(DocumentRegistry.company_id == company_id)
    doc_ids = [d.id for d in docs.all()]
    changes = (
        db.query(ChangeLog)
        .filter(ChangeLog.document_id.in_(doc_ids), ChangeLog.detected_at >= cutoff)
        .order_by(ChangeLog.detected_at.desc())
        .all()
    )
    return [
        {
            "id": c.id, "document_id": c.document_id, "change_type": c.change_type,
            "old_hash": c.old_hash, "new_hash": c.new_hash,
            "detected_at": str(c.detected_at),
        }
        for c in changes
    ]


@router.get("/errors/")
def get_error_logs(company_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(ErrorLog)
    if company_id:
        q = q.filter(ErrorLog.company_id == company_id)
    return [
        {
            "id": e.id, "step": e.step, "error_type": e.error_type,
            "document_url": e.document_url, "error_message": e.error_message,
            "created_at": str(e.created_at),
        }
        for e in q.order_by(ErrorLog.created_at.desc()).limit(200).all()
    ]
