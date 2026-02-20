"""Single-flight guards for job launches."""
from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import timedelta
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import JobRun
from app.utils.time import utc_now_naive

ACTIVE_STATUSES = {"QUEUED", "RUNNING", "RETRY", "RETRYING", "PENDING", "STARTED", "PROGRESS"}

_lock_registry: dict[str, threading.Lock] = {}
_registry_lock = threading.Lock()


def has_active_run(
    db: Session,
    *,
    trigger_types: Iterable[str],
    company_id: Optional[int] = None,
    window_hours: int = 24,
) -> bool:
    now = utc_now_naive()
    cutoff = now - timedelta(hours=window_hours)
    types = [trigger_type.upper() for trigger_type in trigger_types]
    query = db.query(JobRun).filter(
        JobRun.trigger_type.in_(types),
        JobRun.status.in_(list(ACTIVE_STATUSES)),
        JobRun.created_at >= cutoff,
    )
    if company_id is not None:
        query = query.filter(JobRun.company_id == company_id)
    return query.first() is not None


def ensure_no_overlap(
    db: Session,
    *,
    trigger_types: Iterable[str],
    company_id: Optional[int] = None,
    message: str = "Similar run is already in progress.",
) -> None:
    if has_active_run(db, trigger_types=trigger_types, company_id=company_id):
        raise HTTPException(status_code=409, detail=message)


@contextmanager
def acquire_singleflight(bucket: str):
    key = (bucket or "global").strip().lower()
    with _registry_lock:
        lock = _lock_registry.get(key)
        if lock is None:
            lock = threading.Lock()
            _lock_registry[key] = lock

    acquired = lock.acquire(blocking=False)
    if not acquired:
        raise HTTPException(status_code=409, detail=f"{bucket} launch already in progress")
    try:
        yield
    finally:
        lock.release()
