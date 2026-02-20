"""
M3 — Download Agent
Downloads PDFs that are NEW or UPDATED (by ETag + SHA-256 comparison).
Saves to: downloads/{company_slug}/{DocType}/{filename}_v{N}.pdf
"""
import logging
import os
from datetime import datetime
from pathlib import Path
import time
from typing import List, Dict, Any, Optional

import httpx
from sqlalchemy.orm import Session

from app.models import DocumentRegistry, ChangeLog, ErrorLog
from app.utils.http_client import RETRYABLE_STATUSES, request_with_retries
from app.utils.hashing import sha256_file
from app.workflow.state import PipelineState

logger = logging.getLogger(__name__)

MAX_BYTES = 250 * 1024 * 1024  # 250 MB hard limit


def download_agent(state: PipelineState) -> dict:
    """LangGraph node — download all NEW/UPDATED PDFs."""
    from app.database import SessionLocal
    db = SessionLocal()

    downloaded: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = list(state.get("errors", []))

    try:
        for url in state.get("pdf_urls", []):
            try:
                result = _process_one(db, url, state)
                if result:
                    downloaded.append(result)
            except Exception as e:
                msg = f"Download error for {url}: {e}"
                logger.error(f"[M3-DOWNLOAD] {msg}")
                errors.append({"url": url, "step": "download", "error": msg})
                _log_error(db, state["company_id"], url, "download", "DOWNLOAD_FAILED", str(e))
    finally:
        db.close()

    logger.info(f"[M3-DOWNLOAD] {state['company_name']}: {len(downloaded)} docs processed")
    return {"downloaded_docs": downloaded, "errors": errors}


def _process_one(db: Session, url: str, state: PipelineState) -> Optional[Dict[str, Any]]:
    """Process a single URL: ETag check → download → hash → DB update."""
    etag, last_mod = _head_request(url)
    existing: Optional[DocumentRegistry] = (
        db.query(DocumentRegistry).filter(DocumentRegistry.document_url == url).first()
    )

    if existing:
        # ETag / Last-Modified shortcut
        if etag and existing.etag == etag and existing.last_modified_header == last_mod:
            existing.status = "UNCHANGED"
            existing.last_checked = datetime.utcnow()
            db.commit()
            return {"url": url, "status": "UNCHANGED", "doc_id": existing.id}

        # Download and hash-compare
        file_path = _download(url, state["company_slug"], existing.doc_type, state["base_folder"])
        if not file_path:
            existing.status = "FAILED"
            db.commit()
            return {"url": url, "status": "FAILED", "doc_id": existing.id}

        new_hash = sha256_file(file_path)
        if new_hash == existing.file_hash:
            existing.status = "UNCHANGED"
            os.remove(file_path)      # discard duplicate
        else:
            _record_change(db, existing.id, "UPDATED", existing.file_hash, new_hash)
            existing.status = "UPDATED"
            existing.file_hash = new_hash
            existing.local_path = file_path
            existing.file_size_bytes = os.path.getsize(file_path)
            existing.metadata_extracted = False

        existing.etag = etag
        existing.last_modified_header = last_mod
        existing.last_checked = datetime.utcnow()
        db.commit()
        return {"url": url, "status": existing.status, "doc_id": existing.id, "local_path": existing.local_path}

    else:
        # First-time download
        file_path = _download(url, state["company_slug"], "Unknown", state["base_folder"])
        if not file_path:
            return None

        file_hash = sha256_file(file_path)
        record = DocumentRegistry(
            company_id=state["company_id"],
            document_url=url,
            file_hash=file_hash,
            etag=etag,
            last_modified_header=last_mod,
            local_path=file_path,
            doc_type="Unknown",
            file_size_bytes=os.path.getsize(file_path),
            status="NEW",
            last_checked=datetime.utcnow(),
        )
        db.add(record)
        db.flush()
        _record_change(db, record.id, "NEW", None, file_hash)
        db.commit()
        db.refresh(record)
        logger.info(f"[M3-DOWNLOAD] NEW: {url} → {file_path}")
        return {"url": url, "status": "NEW", "doc_id": record.id, "local_path": file_path}


def _head_request(url: str):
    """Returns (etag, last_modified) or (None, None) on failure."""
    try:
        r = request_with_retries(
            "HEAD",
            url,
            follow_redirects=True,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 FinWatch/1.0"},
        )
        return r.headers.get("etag"), r.headers.get("last-modified")
    except Exception:
        return None, None


def _download(url: str, slug: str, doc_type: str, base_folder: str) -> Optional[str]:
    """Stream-download to disk. Returns local path or None on failure."""
    folder = _resolve_folder(base_folder, slug, doc_type)
    filename = _safe_filename(url, folder)
    dest = os.path.join(folder, filename)

    attempts = 3
    for attempt in range(attempts):
        try:
            with httpx.stream(
                "GET",
                url,
                follow_redirects=True,
                timeout=120,
                headers={"User-Agent": "Mozilla/5.0 FinWatch/1.0"},
            ) as r:
                if r.status_code in RETRYABLE_STATUSES and attempt < attempts - 1:
                    time.sleep(min(6.0, 0.7 * (2**attempt)))
                    continue
                r.raise_for_status()

                if r.status_code in {401, 403, 429, 503}:
                    logger.warning(f"[M3-DOWNLOAD] Blocked response for {url}")
                    return None

                ct = r.headers.get("content-type", "")
                if "pdf" not in ct.lower() and not url.lower().endswith(".pdf"):
                    logger.warning(f"[M3-DOWNLOAD] Unexpected content-type '{ct}' for {url}")
                    return None
                size = 0
                with open(dest, "wb") as f:
                    for chunk in r.iter_bytes(65536):
                        size += len(chunk)
                        if size > MAX_BYTES:
                            logger.error(f"[M3-DOWNLOAD] File too large (>250MB): {url}")
                            f.close()
                            os.remove(dest)
                            return None
                        f.write(chunk)
            return dest
        except Exception as e:
            if attempt >= attempts - 1:
                logger.error(f"[M3-DOWNLOAD] Failed {url}: {e}")
                if os.path.exists(dest):
                    os.remove(dest)
                return None
            time.sleep(min(6.0, 0.7 * (2**attempt)))
    return None


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
    path, v = os.path.join(folder, base), 2
    while os.path.exists(path):
        base = f"{stem}_v{v}{ext}"
        path = os.path.join(folder, base)
        v += 1
    return base


def _record_change(db: Session, doc_id: int, change_type: str, old_hash, new_hash):
    db.add(ChangeLog(document_id=doc_id, change_type=change_type, old_hash=old_hash, new_hash=new_hash))


def _log_error(db: Session, company_id: int, url: str, step: str, error_type: str, msg: str):
    try:
        db.add(ErrorLog(company_id=company_id, document_url=url, step=step, error_type=error_type, error_message=msg))
        db.commit()
    except Exception:
        db.rollback()
