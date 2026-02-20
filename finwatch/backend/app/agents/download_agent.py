"""
M3 - Download Agent
Downloads PDFs with stronger validation and deduplication guarantees.
"""
from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ChangeLog, DocumentRegistry, ErrorLog
from app.utils.hashing import sha256_file
from app.utils.http_client import RETRYABLE_STATUSES, is_blocked_response, request_with_retries
from app.utils.time import utc_now_naive
from app.workflow.state import PipelineState

logger = logging.getLogger(__name__)
settings = get_settings()

PDF_SIGNATURE = b"%PDF-"
USER_AGENT = "Mozilla/5.0 FinWatch/2.2"


def download_agent(state: PipelineState) -> dict:
    """LangGraph node - download all NEW/UPDATED PDFs."""
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
            except Exception as exc:
                msg = f"Download error for {url}: {exc}"
                logger.error("[M3-DOWNLOAD] %s", msg)
                errors.append({"url": url, "step": "download", "error": msg})
                _log_error(db, state["company_id"], url, "download", "DOWNLOAD_FAILED", str(exc))
    finally:
        db.close()

    logger.info("[M3-DOWNLOAD] %s: %s docs processed", state["company_name"], len(downloaded))
    return {"downloaded_docs": downloaded, "errors": errors}


def _process_one(db: Session, url: str, state: PipelineState) -> Optional[Dict[str, Any]]:
    etag, last_mod = _head_request(url)
    existing: Optional[DocumentRegistry] = db.query(DocumentRegistry).filter(DocumentRegistry.document_url == url).first()

    if existing and etag and existing.etag == etag and existing.last_modified_header == last_mod:
        existing.status = "UNCHANGED"
        existing.last_checked = utc_now_naive()
        db.commit()
        return {"url": url, "status": "UNCHANGED", "doc_id": existing.id}

    download_outcome = _download(
        url=url,
        slug=state["company_slug"],
        doc_type=existing.doc_type if existing else "Unknown",
        base_folder=state["base_folder"],
    )

    if not download_outcome.get("ok"):
        _log_error(
            db,
            state["company_id"],
            url,
            "download",
            str(download_outcome.get("error_type") or "DOWNLOAD_FAILED"),
            str(download_outcome.get("error_message") or "download failed"),
        )
        if existing:
            existing.status = "FAILED"
            existing.last_checked = utc_now_naive()
            db.commit()
            return {"url": url, "status": "FAILED", "doc_id": existing.id, "reason": download_outcome.get("error_message")}
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
        existing.last_checked = utc_now_naive()
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
        last_checked=utc_now_naive(),
    )
    db.add(record)
    db.flush()
    _record_change(db, record.id, "NEW", None, new_hash)
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
