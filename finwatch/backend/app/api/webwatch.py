"""API router — WebWatch page snapshots and change feed."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import PageSnapshot, PageChange

router = APIRouter()


@router.get("/snapshots")
def list_snapshots(company_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(PageSnapshot)
    if company_id:
        q = q.filter(PageSnapshot.company_id == company_id)
    snaps = q.order_by(PageSnapshot.last_seen.desc()).all()
    return [
        {
            "id": s.id, "company_id": s.company_id, "page_url": s.page_url,
            "content_hash": s.content_hash, "pdf_count": len(s.pdf_urls_found or []),
            "status_code": s.status_code, "is_active": s.is_active,
            "last_seen": str(s.last_seen or ""),
        }
        for s in snaps
    ]


@router.get("/changes")
def list_page_changes(
    company_id: Optional[int] = None,
    change_type: Optional[str] = None,
    hours: int = 24,
    db: Session = Depends(get_db),
):
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = db.query(PageChange).filter(PageChange.detected_at >= cutoff)
    if company_id:
        q = q.filter(PageChange.company_id == company_id)
    if change_type:
        q = q.filter(PageChange.change_type == change_type)

    changes = q.order_by(PageChange.detected_at.desc()).limit(500).all()
    return [
        {
            "id": c.id, "company_id": c.company_id, "page_url": c.page_url,
            "change_type": c.change_type, "diff_summary": c.diff_summary,
            "new_pdf_urls": c.new_pdf_urls, "detected_at": str(c.detected_at),
        }
        for c in changes
    ]


@router.get("/changes/{change_id}/diff")
def get_diff(change_id: int, db: Session = Depends(get_db)):
    """Return old_text and new_text for a specific page change."""
    c = db.get(PageChange, change_id)
    if not c:
        from fastapi import HTTPException
        raise HTTPException(404, "Change not found")
    return {
        "change_type": c.change_type, "page_url": c.page_url,
        "old_text": c.old_text, "new_text": c.new_text,
        "diff_summary": c.diff_summary, "detected_at": str(c.detected_at),
    }
