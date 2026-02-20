"""
M3 - Download Agent
Downloads PDFs with stronger validation and deduplication guarantees.
"""
from __future__ import annotations

import logging
import os
import shutil
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ChangeLog, DocumentRegistry, ErrorLog, IngestionRetry
from app.utils.hashing import sha256_file
from app.utils.http_client import RETRYABLE_STATUSES, is_blocked_response, request_with_retries
from app.utils.time import utc_now_naive
from app.workflow.state import PipelineState

logger = logging.getLogger(__name__)
settings = get_settings()

PDF_SIGNATURE = b"%PDF-"
USER_AGENT = "Mozilla/5.0 FinWatch/2.2"
MAX_RETRY_ATTEMPTS = 3


def download_agent(state: PipelineState) -> dict:
    """LangGraph node - download all NEW/UPDATED PDFs."""
    from app.database import SessionLocal

    db = SessionLocal()
    downloaded: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = list(state.get("errors", []))
    source_map = dict(state.get("pdf_sources", {}))

    try:
        queue = _build_download_queue(db, state)
        for url in queue:
            try:
                result = _process_one(db, url, state, source_map.get(url))
                if result:
                    downloaded.append(result)
            except Exception as exc:
                msg = f"Download error for {url}: {exc}"
                logger.error("[M3-DOWNLOAD] %s", msg)
                errors.append({"url": url, "step": "download", "error": msg})
                _log_error(db, state["company_id"], url, "download", "DOWNLOAD_FAILED", str(exc))
    finally:
        db.close()

    logger.info("[M3-DOWNLOAD] %s: %s docs processed", state["company_name"], len(downloaded))
    return {"downloaded_docs": downloaded, "errors": errors}


def _process_one(db: Session, url: str, state: PipelineState, source_meta: Optional[dict] = None) -> Optional[Dict[str, Any]]:
    source_meta = source_meta or _infer_source_from_url(url)
    seen_at = utc_now_naive()
    etag, last_mod = _head_request(url)
    existing: Optional[DocumentRegistry] = db.query(DocumentRegistry).filter(DocumentRegistry.document_url == url).first()

    if existing and etag and existing.etag == etag and existing.last_modified_header == last_mod:
        existing.status = "UNCHANGED"
        existing.last_checked = seen_at
        existing.last_seen_at = seen_at
        _apply_source_metadata(existing, source_meta, seen_at)
        _resolve_retry_entry(db, state["company_id"], url)
        db.commit()
        return {"url": url, "status": "UNCHANGED", "doc_id": existing.id}

    download_outcome = _download(
        url=url,
        slug=state["company_slug"],
        doc_type=existing.doc_type if existing else "Unknown",
        base_folder=state["base_folder"],
    )

    if not download_outcome.get("ok"):
        error_type = str(download_outcome.get("error_type") or "DOWNLOAD_FAILED")
        error_message = str(download_outcome.get("error_message") or "download failed")
        _log_error(
            db,
            state["company_id"],
            url,
            "download",
            error_type,
            error_message,
        )
        _upsert_retry_entry(
            db,
            company_id=state["company_id"],
            url=url,
            reason_code=error_type,
            error_message=error_message,
        )
        if existing:
            existing.status = "FAILED"
            existing.last_checked = seen_at
            existing.last_seen_at = seen_at
            _apply_source_metadata(existing, source_meta, seen_at)
            db.commit()
            return {"url": url, "status": "FAILED", "doc_id": existing.id, "reason": error_message}
        return None

    file_path = str(download_outcome["path"])
    new_hash = sha256_file(file_path)
    dedupe_target = _resolve_global_dedupe_path(db, new_hash, exclude_doc_id=existing.id if existing else None)
    deduped = False
    if dedupe_target and dedupe_target != file_path:
        deduped = True
        _safe_remove(file_path)
        file_path = dedupe_target

    if existing:
        if new_hash == existing.file_hash:
            existing.status = "UNCHANGED"
            if not deduped:
                _safe_remove(file_path)
        else:
            _record_change(db, existing.id, "UPDATED", existing.file_hash, new_hash)
            existing.status = "UPDATED"
            existing.file_hash = new_hash
            existing.local_path = file_path
            existing.file_size_bytes = _safe_size(file_path)
            existing.metadata_extracted = False

        existing.etag = etag
        existing.last_modified_header = last_mod
        existing.last_checked = seen_at
        existing.last_seen_at = seen_at
        _apply_source_metadata(existing, source_meta, seen_at)
        _resolve_retry_entry(db, state["company_id"], url)
        db.commit()
        return {
            "url": url,
            "status": existing.status,
            "doc_id": existing.id,
            "local_path": existing.local_path,
            "deduplicated": deduped,
        }

    record = DocumentRegistry(
        company_id=state["company_id"],
        document_url=url,
        file_hash=new_hash,
        etag=etag,
        last_modified_header=last_mod,
        local_path=file_path,
        doc_type="Unknown",
        file_size_bytes=_safe_size(file_path),
        status="NEW",
        source_type=source_meta.get("source_type"),
        source_domain=source_meta.get("source_domain"),
        discovery_strategy=source_meta.get("discovery_strategy"),
        first_seen_at=seen_at,
        last_seen_at=seen_at,
        last_checked=seen_at,
    )
    db.add(record)
    db.flush()
    _record_change(db, record.id, "NEW", None, new_hash)
    _resolve_retry_entry(db, state["company_id"], url)
    db.commit()
    db.refresh(record)
    logger.info("[M3-DOWNLOAD] NEW: %s -> %s", url, file_path)
    return {
        "url": url,
        "status": "NEW",
        "doc_id": record.id,
        "local_path": file_path,
        "deduplicated": deduped,
    }


def _build_download_queue(db: Session, state: PipelineState) -> List[str]:
    now = utc_now_naive()
    seen = set()
    queue: List[str] = []

    for url in state.get("pdf_urls", []):
        if not url or url in seen:
            continue
        seen.add(url)
        queue.append(url)

    retry_rows = (
        db.query(IngestionRetry)
        .filter(
            IngestionRetry.company_id == state["company_id"],
            IngestionRetry.status == "PENDING",
            IngestionRetry.failure_count < MAX_RETRY_ATTEMPTS,
            ((IngestionRetry.next_retry_at.is_(None)) | (IngestionRetry.next_retry_at <= now)),
        )
        .order_by(IngestionRetry.next_retry_at.asc(), IngestionRetry.created_at.asc())
        .limit(50)
        .all()
    )
    for row in retry_rows:
        if row.document_url and row.document_url not in seen:
            queue.append(row.document_url)
            seen.add(row.document_url)
    return queue


def _head_request(url: str):
    try:
        response = request_with_retries(
            "HEAD",
            url,
            follow_redirects=True,
            timeout=10,
            headers={"User-Agent": USER_AGENT},
        )
        if is_blocked_response(response):
            return None, None
        return response.headers.get("etag"), response.headers.get("last-modified")
    except Exception:
        return None, None


def _download(url: str, slug: str, doc_type: str, base_folder: str) -> dict:
    folder = _resolve_folder(base_folder, slug, doc_type)
    filename = _safe_filename(url, folder)
    final_dest = os.path.join(folder, filename)
    temp_dest = f"{final_dest}.part"

    attempts = 3
    max_bytes = int(settings.download_max_bytes or 262144000)

    for attempt in range(attempts):
        try:
            with httpx.stream(
                "GET",
                url,
                follow_redirects=True,
                timeout=120,
                headers={"User-Agent": USER_AGENT},
            ) as response:
                if response.status_code in RETRYABLE_STATUSES and attempt < attempts - 1:
                    time.sleep(min(6.0, 0.7 * (2**attempt)))
                    continue
                if is_blocked_response(response):
                    return {"ok": False, "error_type": "DOWNLOAD_BLOCKED", "error_message": f"Blocked response ({response.status_code})"}

                response.raise_for_status()
                content_type = (response.headers.get("content-type") or "").lower()
                if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                    return {"ok": False, "error_type": "INVALID_CONTENT_TYPE", "error_message": f"Unexpected content-type '{content_type}'"}

                size = 0
                with open(temp_dest, "wb") as handle:
                    for chunk in response.iter_bytes(65536):
                        size += len(chunk)
                        if size > max_bytes:
                            handle.close()
                            _safe_remove(temp_dest)
                            return {
                                "ok": False,
                                "error_type": "FILE_TOO_LARGE",
                                "error_message": f"File exceeded max size {max_bytes} bytes",
                            }
                        handle.write(chunk)

            if not _looks_like_pdf(temp_dest):
                quarantined = _quarantine_file(base_folder, slug, temp_dest, "invalid_signature")
                return {
                    "ok": False,
                    "error_type": "INVALID_PDF_SIGNATURE",
                    "error_message": f"Downloaded file is not a valid PDF signature. quarantined={quarantined}",
                }

            os.replace(temp_dest, final_dest)
            return {"ok": True, "path": final_dest}
        except Exception as exc:
            if attempt >= attempts - 1:
                _safe_remove(temp_dest)
                return {"ok": False, "error_type": "DOWNLOAD_FAILED", "error_message": str(exc)}
            time.sleep(min(6.0, 0.7 * (2**attempt)))
    return {"ok": False, "error_type": "DOWNLOAD_FAILED", "error_message": "Retries exhausted"}


def _resolve_global_dedupe_path(db: Session, file_hash: str, exclude_doc_id: Optional[int] = None) -> Optional[str]:
    query = db.query(DocumentRegistry).filter(
        DocumentRegistry.file_hash == file_hash,
        DocumentRegistry.local_path.isnot(None),
    )
    if exclude_doc_id is not None:
        query = query.filter(DocumentRegistry.id != exclude_doc_id)
    existing = query.order_by(DocumentRegistry.created_at.asc()).first()
    if not existing or not existing.local_path:
        return None
    return existing.local_path if os.path.exists(existing.local_path) else None


def _infer_source_from_url(url: str) -> dict:
    domain = (urlparse(url).netloc or "").lower()
    source_type = "REGULATORY" if "sec.gov" in domain else "WEBSITE"
    return {
        "source_type": source_type,
        "source_domain": domain,
        "discovery_strategy": "UNKNOWN",
    }


def _apply_source_metadata(record: DocumentRegistry, source_meta: dict, seen_at) -> None:
    if source_meta.get("source_type"):
        record.source_type = source_meta["source_type"]
    if source_meta.get("source_domain"):
        record.source_domain = source_meta["source_domain"]
    if source_meta.get("discovery_strategy"):
        record.discovery_strategy = source_meta["discovery_strategy"]
    if not record.first_seen_at:
        record.first_seen_at = seen_at
    record.last_seen_at = seen_at


def _upsert_retry_entry(db: Session, *, company_id: int, url: str, reason_code: str, error_message: str) -> None:
    now = utc_now_naive()
    retry = (
        db.query(IngestionRetry)
        .filter(
            IngestionRetry.company_id == company_id,
            IngestionRetry.document_url == url,
            IngestionRetry.status.in_(["PENDING", "DEAD"]),
        )
        .order_by(IngestionRetry.id.desc())
        .first()
    )
    if retry:
        retry.failure_count = int(retry.failure_count or 0) + 1
        retry.reason_code = reason_code
        retry.last_error = error_message[:2000]
        retry.last_attempt_at = now
    else:
        retry = IngestionRetry(
            company_id=company_id,
            document_url=url,
            source_domain=(urlparse(url).netloc or "").lower(),
            reason_code=reason_code,
            failure_count=1,
            status="PENDING",
            last_error=error_message[:2000],
            last_attempt_at=now,
        )
        db.add(retry)

    if retry.failure_count >= MAX_RETRY_ATTEMPTS:
        retry.status = "DEAD"
        retry.next_retry_at = None
        db.add(
            ErrorLog(
                company_id=company_id,
                document_url=url,
                step="download",
                error_type="DEAD_LETTER",
                error_message=f"{reason_code}: {error_message}"[:2000],
            )
        )
    else:
        retry.status = "PENDING"
        backoff_minutes = min(240, (2 ** retry.failure_count) * 5)
        retry.next_retry_at = now + timedelta(minutes=backoff_minutes)
    db.commit()


def _resolve_retry_entry(db: Session, company_id: int, url: str) -> None:
    rows = (
        db.query(IngestionRetry)
        .filter(
            IngestionRetry.company_id == company_id,
            IngestionRetry.document_url == url,
            IngestionRetry.status.in_(["PENDING", "DEAD"]),
        )
        .all()
    )
    if not rows:
        return
    now = utc_now_naive()
    for row in rows:
        row.status = "RESOLVED"
        row.next_retry_at = None
    db.flush()


def _looks_like_pdf(path: str) -> bool:
    try:
        with open(path, "rb") as handle:
            prefix = handle.read(len(PDF_SIGNATURE))
        return prefix == PDF_SIGNATURE
    except Exception:
        return False


def _quarantine_file(base_folder: str, slug: str, source_path: str, reason: str) -> str:
    quarantine_folder = Path(base_folder) / slug / "_quarantine"
    quarantine_folder.mkdir(parents=True, exist_ok=True)
    base_name = Path(source_path).name.replace(".part", "")
    target = quarantine_folder / f"{reason}_{base_name}"
    suffix = 2
    while target.exists():
        target = quarantine_folder / f"{reason}_{suffix}_{base_name}"
        suffix += 1
    try:
        shutil.move(source_path, str(target))
        return str(target)
    except Exception:
        _safe_remove(source_path)
        return ""


def _resolve_folder(base: str, slug: str, doc_type: str) -> str:
    type_map = {
        "Annual Report": "AnnualReports",
        "Quarterly Report": "QuarterlyReports",
        "Financial Statement": "FinancialStatements",
        "ESG": "ESGReports",
    }
    sub = type_map.get(doc_type, "Other")
    folder = os.path.join(base, slug, sub)
    Path(folder).mkdir(parents=True, exist_ok=True)
    return folder


def _safe_filename(url: str, folder: str) -> str:
    base = os.path.basename(url.split("?")[0]) or "document.pdf"
    if not base.lower().endswith(".pdf"):
        base += ".pdf"
    stem, ext = os.path.splitext(base)
    path, version = os.path.join(folder, base), 2
    while os.path.exists(path):
        base = f"{stem}_v{version}{ext}"
        path = os.path.join(folder, base)
        version += 1
    return base


def _safe_size(path: str) -> Optional[int]:
    try:
        return os.path.getsize(path)
    except Exception:
        return None


def _safe_remove(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _record_change(db: Session, doc_id: int, change_type: str, old_hash, new_hash):
    db.add(ChangeLog(document_id=doc_id, change_type=change_type, old_hash=old_hash, new_hash=new_hash))


def _log_error(db: Session, company_id: int, url: str, step: str, error_type: str, msg: str):
    try:
        db.add(ErrorLog(company_id=company_id, document_url=url, step=step, error_type=error_type, error_message=msg))
        db.commit()
    except Exception:
        db.rollback()
