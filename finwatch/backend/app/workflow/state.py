"""
Pipeline State — shared TypedDict passed through every LangGraph node.
"""
from typing import TypedDict, List, Dict, Any, Optional


class PipelineState(TypedDict):
    # ── Company context ────────────────────────────────────────────────────
    company_id: int
    company_name: str
    company_slug: str
    website_url: str
    base_folder: str
    crawl_depth: int

    # ── M1 Crawl output ────────────────────────────────────────────────────
    pdf_urls: List[str]             # all discovered PDF URLs
    pdf_sources: Dict[str, Dict[str, Any]]  # url -> source metadata
    crawl_errors: List[str]

    # ── M2 WebWatch output ─────────────────────────────────────────────────
    page_changes: List[Dict[str, Any]]
    has_changes: bool               # True if any doc or page changes exist

    # ── M3 Download output ─────────────────────────────────────────────────
    downloaded_docs: List[Dict[str, Any]]   # {url, status, doc_id, local_path, full_text}
    errors: List[Dict[str, str]]

    # ── M7 Excel output ────────────────────────────────────────────────────
    excel_path: Optional[str]

    # ── M8 Email output ────────────────────────────────────────────────────
    email_sent: bool
