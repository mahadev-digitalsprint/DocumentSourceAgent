"""API router for crawler diagnostics and control-plane visibility."""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company, CrawlDiagnostic
from app.utils.crawl_control import domain_control
from app.utils.time import utc_now_naive

router = APIRouter()


def _base_diagnostic_query(
    db: Session,
    *,
    hours: int,
    company_id: Optional[int],
    strategy: Optional[str],
    domain: Optional[str],
    blocked: Optional[bool],
):
    cutoff = utc_now_naive() - timedelta(hours=hours)
    query = db.query(CrawlDiagnostic).filter(CrawlDiagnostic.created_at >= cutoff)
    if company_id is not None:
        query = query.filter(CrawlDiagnostic.company_id == company_id)
    if strategy:
        query = query.filter(CrawlDiagnostic.strategy == strategy)
    if domain:
        query = query.filter(func.lower(CrawlDiagnostic.domain) == domain.lower())
    if blocked is not None:
        query = query.filter(CrawlDiagnostic.blocked == blocked)
    return query


@router.get("/diagnostics")
def list_diagnostics(
    hours: int = Query(default=24, ge=1, le=24 * 30),
    company_id: Optional[int] = None,
    strategy: Optional[str] = None,
    domain: Optional[str] = None,
    blocked: Optional[bool] = None,
    limit: int = Query(default=300, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    rows = (
        _base_diagnostic_query(
            db,
            hours=hours,
            company_id=company_id,
            strategy=strategy,
            domain=domain,
            blocked=blocked,
        )
        .outerjoin(Company, Company.id == CrawlDiagnostic.company_id)
        .with_entities(CrawlDiagnostic, Company.company_name)
        .order_by(CrawlDiagnostic.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": diagnostic.id,
            "company_id": diagnostic.company_id,
            "company_name": company_name,
            "domain": diagnostic.domain,
            "strategy": diagnostic.strategy,
            "page_url": diagnostic.page_url,
            "status_code": diagnostic.status_code,
            "blocked": bool(diagnostic.blocked),
            "error_message": diagnostic.error_message,
            "retry_count": diagnostic.retry_count,
            "duration_ms": diagnostic.duration_ms,
            "created_at": str(diagnostic.created_at or ""),
        }
        for diagnostic, company_name in rows
    ]


@router.get("/diagnostics/summary")
def diagnostics_summary(
    hours: int = Query(default=24, ge=1, le=24 * 30),
    company_id: Optional[int] = None,
    strategy: Optional[str] = None,
    domain: Optional[str] = None,
    db: Session = Depends(get_db),
):
    base = _base_diagnostic_query(
        db,
        hours=hours,
        company_id=company_id,
        strategy=strategy,
        domain=domain,
        blocked=None,
    )

    total_requests = base.count()
    blocked_requests = base.filter(CrawlDiagnostic.blocked == True).count()
    error_requests = (
        base.filter(
            or_(
                CrawlDiagnostic.error_message.isnot(None),
                and_(CrawlDiagnostic.status_code.isnot(None), CrawlDiagnostic.status_code >= 500),
            )
        ).count()
    )
    avg_duration = base.with_entities(func.avg(CrawlDiagnostic.duration_ms)).scalar() or 0
    unique_domains = base.with_entities(func.count(func.distinct(CrawlDiagnostic.domain))).scalar() or 0
    unique_companies = base.with_entities(func.count(func.distinct(CrawlDiagnostic.company_id))).scalar() or 0

    durations = [
        int(duration)
        for (duration,) in base.with_entities(CrawlDiagnostic.duration_ms)
        .filter(CrawlDiagnostic.duration_ms.isnot(None))
        .all()
    ]
    durations.sort()
    p95_duration = 0
    if durations:
        idx = max(0, math.ceil(0.95 * len(durations)) - 1)
        p95_duration = durations[idx]

    strategy_rows = (
        base.with_entities(CrawlDiagnostic.strategy, func.count(CrawlDiagnostic.id).label("count"))
        .group_by(CrawlDiagnostic.strategy)
        .order_by(func.count(CrawlDiagnostic.id).desc())
        .all()
    )
    blocked_domains = domain_control.blocked_domains()

    return {
        "window_hours": hours,
        "total_requests": int(total_requests),
        "blocked_requests": int(blocked_requests),
        "error_requests": int(error_requests),
        "avg_duration_ms": round(float(avg_duration), 2) if avg_duration else 0,
        "p95_duration_ms": int(p95_duration),
        "unique_domains": int(unique_domains),
        "unique_companies": int(unique_companies),
        "active_domain_cooldowns": len(blocked_domains),
        "strategy_breakdown": [
            {"strategy": row[0] or "UNKNOWN", "count": int(row[1] or 0)}
            for row in strategy_rows
        ],
    }


@router.get("/cooldowns")
def list_cooldowns():
    return {"blocked_domains": domain_control.blocked_domains()}


@router.delete("/cooldowns")
def clear_cooldowns():
    domain_control.clear()
    return {"cleared": True}


@router.delete("/cooldowns/{domain}")
def clear_cooldown_for_domain(domain: str):
    domain_control.unblock(domain.strip().lower())
    return {"cleared": True, "domain": domain.strip().lower()}
