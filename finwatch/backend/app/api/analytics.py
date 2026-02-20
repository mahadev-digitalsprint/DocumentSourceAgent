"""Analytics API for operational and document intelligence summaries."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChangeLog, Company, DocumentRegistry, ErrorLog, JobRun, PageChange

router = APIRouter()


@router.get("/overview")
def overview(hours: int = Query(default=24, ge=1, le=24 * 30), db: Session = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    return {
        "window_hours": hours,
        "companies_total": db.query(func.count(Company.id)).scalar() or 0,
        "companies_active": db.query(func.count(Company.id)).filter(Company.active == True).scalar() or 0,
        "documents_total": db.query(func.count(DocumentRegistry.id)).scalar() or 0,
        "documents_metadata_extracted": db.query(func.count(DocumentRegistry.id))
        .filter(DocumentRegistry.metadata_extracted == True)
        .scalar()
        or 0,
        "document_changes": db.query(func.count(ChangeLog.id)).filter(ChangeLog.detected_at >= cutoff).scalar() or 0,
        "page_changes": db.query(func.count(PageChange.id)).filter(PageChange.detected_at >= cutoff).scalar() or 0,
        "errors": db.query(func.count(ErrorLog.id)).filter(ErrorLog.created_at >= cutoff).scalar() or 0,
        "job_runs": db.query(func.count(JobRun.id)).filter(JobRun.created_at >= cutoff).scalar() or 0,
    }


@router.get("/doc-type-distribution")
def doc_type_distribution(limit: int = Query(default=25, ge=1, le=100), db: Session = Depends(get_db)):
    rows = (
        db.query(DocumentRegistry.doc_type, func.count(DocumentRegistry.id).label("count"))
        .group_by(DocumentRegistry.doc_type)
        .order_by(func.count(DocumentRegistry.id).desc())
        .limit(limit)
        .all()
    )
    return [{"doc_type": row[0] or "UNKNOWN", "count": int(row[1])} for row in rows]


@router.get("/company-activity")
def company_activity(
    hours: int = Query(default=168, ge=1, le=24 * 90),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    doc_counts = (
        db.query(DocumentRegistry.company_id, func.count(DocumentRegistry.id).label("documents"))
        .group_by(DocumentRegistry.company_id)
        .subquery()
    )
    doc_change_counts = (
        db.query(DocumentRegistry.company_id, func.count(ChangeLog.id).label("doc_changes"))
        .join(ChangeLog, ChangeLog.document_id == DocumentRegistry.id)
        .filter(ChangeLog.detected_at >= cutoff)
        .group_by(DocumentRegistry.company_id)
        .subquery()
    )
    page_change_counts = (
        db.query(PageChange.company_id, func.count(PageChange.id).label("page_changes"))
        .filter(PageChange.detected_at >= cutoff)
        .group_by(PageChange.company_id)
        .subquery()
    )

    rows = (
        db.query(
            Company.id,
            Company.company_name,
            Company.active,
            func.coalesce(doc_counts.c.documents, 0),
            func.coalesce(doc_change_counts.c.doc_changes, 0),
            func.coalesce(page_change_counts.c.page_changes, 0),
        )
        .outerjoin(doc_counts, doc_counts.c.company_id == Company.id)
        .outerjoin(doc_change_counts, doc_change_counts.c.company_id == Company.id)
        .outerjoin(page_change_counts, page_change_counts.c.company_id == Company.id)
        .order_by((func.coalesce(doc_change_counts.c.doc_changes, 0) + func.coalesce(page_change_counts.c.page_changes, 0)).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "company_id": row[0],
            "company_name": row[1],
            "active": bool(row[2]),
            "documents_total": int(row[3] or 0),
            "document_changes_window": int(row[4] or 0),
            "page_changes_window": int(row[5] or 0),
        }
        for row in rows
    ]


@router.get("/change-trend")
def change_trend(
    days: int = Query(default=14, ge=1, le=120),
    company_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(days=days)

    doc_query = db.query(
        func.date(ChangeLog.detected_at).label("day"),
        func.count(ChangeLog.id).label("count"),
    ).join(DocumentRegistry, ChangeLog.document_id == DocumentRegistry.id)
    if company_id is not None:
        doc_query = doc_query.filter(DocumentRegistry.company_id == company_id)
    doc_rows = (
        doc_query.filter(ChangeLog.detected_at >= cutoff)
        .group_by(func.date(ChangeLog.detected_at))
        .all()
    )

    page_query = db.query(
        func.date(PageChange.detected_at).label("day"),
        func.count(PageChange.id).label("count"),
    )
    if company_id is not None:
        page_query = page_query.filter(PageChange.company_id == company_id)
    page_rows = (
        page_query.filter(PageChange.detected_at >= cutoff)
        .group_by(func.date(PageChange.detected_at))
        .all()
    )

    day_map = {}
    for day, count in doc_rows:
        key = str(day)
        day_map.setdefault(key, {"date": key, "document_changes": 0, "page_changes": 0})
        day_map[key]["document_changes"] = int(count or 0)
    for day, count in page_rows:
        key = str(day)
        day_map.setdefault(key, {"date": key, "document_changes": 0, "page_changes": 0})
        day_map[key]["page_changes"] = int(count or 0)

    return sorted(day_map.values(), key=lambda row: row["date"])


@router.get("/job-runs")
def job_runs(
    hours: int = Query(default=24, ge=1, le=24 * 30),
    db: Session = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(JobRun.status, func.count(JobRun.id).label("count"))
        .filter(JobRun.created_at >= cutoff)
        .group_by(JobRun.status)
        .all()
    )
    return {
        "window_hours": hours,
        "status_breakdown": [{"status": row[0], "count": int(row[1] or 0)} for row in rows],
    }


@router.get("/doc-change-types")
def doc_change_types(
    hours: int = Query(default=168, ge=1, le=24 * 90),
    company_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    query = db.query(ChangeLog.change_type, func.count(ChangeLog.id).label("count")).join(
        DocumentRegistry, ChangeLog.document_id == DocumentRegistry.id
    )
    if company_id is not None:
        query = query.filter(DocumentRegistry.company_id == company_id)

    rows = (
        query.filter(ChangeLog.detected_at >= cutoff)
        .group_by(ChangeLog.change_type)
        .order_by(func.count(ChangeLog.id).desc())
        .all()
    )
    return [{"change_type": row[0] or "UNKNOWN", "count": int(row[1] or 0)} for row in rows]
