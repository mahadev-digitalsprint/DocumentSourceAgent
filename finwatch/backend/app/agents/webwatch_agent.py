"""
M2 — WebWatch Agent
Monitors every webpage of a company's site for:
  - PAGE_ADDED       : new URL discovered never seen before
  - PAGE_DELETED     : previously known URL now returns 404 or error
  - CONTENT_CHANGED  : page text hash differs from last snapshot
  - NEW_DOC_LINKED   : new PDF URLs found on the page not previously linked

Stores snapshots in `page_snapshots`, diffs in `page_changes`.
"""
import difflib
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import PageSnapshot, PageChange, Company
from app.utils.hashing import sha256_text
from app.workflow.state import PipelineState

logger = logging.getLogger(__name__)
settings = get_settings()

PDF_RE = re.compile(r'https?://[^\s\'"<>]+\.pdf(?:\?[^\s\'"<>]*)?', re.IGNORECASE)
MAX_PAGES = 200
MAX_TEXT_LEN = 50_000


def webwatch_agent(state: PipelineState) -> dict:
    """LangGraph node — snapshot every page and detect diffs."""
    from app.database import SessionLocal
    db = SessionLocal()

    detected_changes: List[Dict[str, Any]] = []
    new_pdf_urls: List[str] = list(state.get("pdf_urls", []))

    try:
        all_pages = _discover_pages(state["website_url"], state.get("crawl_depth", 3))
        logger.info(f"[M2-WEBWATCH] {state['company_name']}: {len(all_pages)} pages discovered")

        db_snapshots: Dict[str, PageSnapshot] = {
            s.page_url: s
            for s in db.query(PageSnapshot).filter(PageSnapshot.company_id == state["company_id"]).all()
        }

        # Check for DELETED pages (known URLs no longer discovered)
        known_urls = set(db_snapshots.keys())
        live_urls = set(all_pages)
        deleted = known_urls - live_urls
        for url in deleted:
            snap = db_snapshots[url]
            if snap.is_active:
                snap.is_active = False
                _save_change(db, state["company_id"], url, "PAGE_DELETED",
                             old_text=snap.content_text, new_text=None,
                             diff_summary=f"Page no longer reachable: {url}",
                             old_hash=snap.content_hash, new_hash=None)
                detected_changes.append({"change_type": "PAGE_DELETED", "page_url": url})
                logger.info(f"[M2-WEBWATCH] PAGE_DELETED: {url}")

        # Process each discovered page
        for page_url in all_pages:
            try:
                resp = httpx.get(page_url, follow_redirects=True, timeout=15,
                                 headers={"User-Agent": "Mozilla/5.0 FinWatch/1.0"})
                status_code = resp.status_code

                soup = BeautifulSoup(resp.text, "html.parser")
                page_text = soup.get_text(separator="\n", strip=True)[:MAX_TEXT_LEN]
                page_hash = sha256_text(page_text)

                # Extract PDF links from this page
                page_base = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"
                pdf_on_page: List[str] = []
                for tag in soup.find_all("a", href=True):
                    href = urljoin(page_base, tag["href"])
                    if href.lower().endswith(".pdf"):
                        pdf_on_page.append(href)
                for match in PDF_RE.findall(resp.text):
                    pdf_on_page.append(match)
                pdf_on_page = list(set(pdf_on_page))

                existing: PageSnapshot = db_snapshots.get(page_url)

                if existing is None:
                    # Brand new page
                    snap = PageSnapshot(
                        company_id=state["company_id"],
                        page_url=page_url,
                        content_hash=page_hash,
                        content_text=page_text,
                        pdf_urls_found=pdf_on_page,
                        status_code=status_code,
                        is_active=True,
                        last_seen=datetime.utcnow(),
                    )
                    db.add(snap)
                    _save_change(db, state["company_id"], page_url, "PAGE_ADDED",
                                 old_text=None, new_text=page_text,
                                 diff_summary=f"New page discovered: {page_url}",
                                 old_hash=None, new_hash=page_hash,
                                 new_pdf_urls=pdf_on_page)
                    detected_changes.append({"change_type": "PAGE_ADDED", "page_url": page_url})
                    new_pdf_urls.extend(pdf_on_page)
                    logger.info(f"[M2-WEBWATCH] PAGE_ADDED: {page_url}")

                else:
                    updates: Dict = {"last_seen": datetime.utcnow(), "status_code": status_code, "is_active": True}

                    # Check content change
                    if existing.content_hash != page_hash:
                        diff_summary = _make_diff_summary(existing.content_text or "", page_text)
                        _save_change(db, state["company_id"], page_url, "CONTENT_CHANGED",
                                     old_text=existing.content_text, new_text=page_text,
                                     diff_summary=diff_summary,
                                     old_hash=existing.content_hash, new_hash=page_hash)
                        updates.update({"content_hash": page_hash, "content_text": page_text})
                        detected_changes.append({
                            "change_type": "CONTENT_CHANGED",
                            "page_url": page_url,
                            "diff_summary": diff_summary[:200],
                        })
                        logger.info(f"[M2-WEBWATCH] CONTENT_CHANGED: {page_url}")

                    # Check for new PDF links on page
                    old_pdfs: Set[str] = set(existing.pdf_urls_found or [])
                    new_pdfs = [p for p in pdf_on_page if p not in old_pdfs]
                    if new_pdfs:
                        _save_change(db, state["company_id"], page_url, "NEW_DOC_LINKED",
                                     old_text=None, new_text=None,
                                     diff_summary=f"{len(new_pdfs)} new PDF(s) linked: {', '.join(new_pdfs[:3])}",
                                     old_hash=existing.content_hash, new_hash=page_hash,
                                     new_pdf_urls=new_pdfs)
                        updates["pdf_urls_found"] = pdf_on_page
                        detected_changes.append({
                            "change_type": "NEW_DOC_LINKED",
                            "page_url": page_url,
                            "new_pdfs": new_pdfs,
                        })
                        new_pdf_urls.extend(new_pdfs)
                        logger.info(f"[M2-WEBWATCH] NEW_DOC_LINKED: {page_url} ({len(new_pdfs)} new PDFs)")

                    for k, v in updates.items():
                        setattr(existing, k, v)

                db.commit()

            except Exception as e:
                logger.warning(f"[M2-WEBWATCH] Error on {page_url}: {e}")

    finally:
        db.close()

    # Merge new PDF URLs found by WebWatch with those from crawl
    all_pdfs = list(set(state.get("pdf_urls", []) + new_pdf_urls))
    return {
        "pdf_urls": all_pdfs,
        "page_changes": detected_changes,
        "has_changes": len(detected_changes) > 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
def _discover_pages(base_url: str, depth: int) -> List[str]:
    """Return all internal page URLs up to max depth."""
    visited = set()
    queue = [(base_url, 0)]
    base_domain = urlparse(base_url).netloc

    while queue:
        url, d = queue.pop(0)
        if url in visited or d > depth or len(visited) > MAX_PAGES:
            continue
        visited.add(url)
        try:
            r = httpx.get(url, follow_redirects=True, timeout=10,
                          headers={"User-Agent": "Mozilla/5.0 FinWatch/1.0"})
            soup = BeautifulSoup(r.text, "html.parser")
            page_base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            for tag in soup.find_all("a", href=True):
                full = urljoin(page_base, tag["href"])
                if urlparse(full).netloc == base_domain and full not in visited:
                    if not any(full.endswith(e) for e in [".pdf", ".jpg", ".png", ".css", ".js"]):
                        queue.append((full, d + 1))
        except Exception:
            pass

    return list(visited)


def _make_diff_summary(old: str, new: str) -> str:
    """Generate a short human-readable diff summary."""
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm="", n=0))
    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))

    samples = [l[1:].strip() for l in diff if l.startswith("+") and not l.startswith("+++")][:3]
    sample_text = " | ".join(samples)[:200]
    return f"+{added} lines added, -{removed} lines removed. Sample: {sample_text}"


def _save_change(db: Session, company_id: int, page_url: str, change_type: str,
                 old_text, new_text, diff_summary: str,
                 old_hash=None, new_hash=None, new_pdf_urls=None):
    change = PageChange(
        company_id=company_id,
        page_url=page_url,
        change_type=change_type,
        old_text=(old_text or "")[:50_000],
        new_text=(new_text or "")[:50_000],
        diff_summary=diff_summary,
        new_pdf_urls=new_pdf_urls or [],
        old_hash=old_hash,
        new_hash=new_hash,
    )
    db.add(change)
