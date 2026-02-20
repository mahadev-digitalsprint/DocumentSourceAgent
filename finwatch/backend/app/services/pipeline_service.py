"""Pipeline execution helpers shared across APIs."""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.models import Company

logger = logging.getLogger(__name__)


def build_initial_state(company: Company, base_folder: str) -> Dict[str, Any]:
    return {
        "company_id": company.id,
        "company_name": company.company_name,
        "company_slug": company.company_slug,
        "website_url": company.website_url,
        "base_folder": base_folder,
        "crawl_depth": company.crawl_depth or 3,
        "pdf_urls": [],
        "pdf_sources": {},
        "crawl_errors": [],
        "page_changes": [],
        "has_changes": False,
        "downloaded_docs": [],
        "errors": [],
        "excel_path": None,
        "email_sent": False,
    }


def run_company_sync(company: Company, base_folder: str) -> Dict[str, Any]:
    """Run the full pipeline graph synchronously for one company."""
    from app.workflow.graph import pipeline_graph

    initial_state = build_initial_state(company, base_folder)
    logger.info("[DIRECT] Pipeline start for %s", company.company_name)
    result = pipeline_graph.invoke(initial_state)
    summary = {
        "company": company.company_name,
        "pdfs_found": len(result.get("pdf_urls", [])),
        "docs_downloaded": len(result.get("downloaded_docs", [])),
        "has_changes": bool(result.get("has_changes")),
        "errors": len(result.get("errors", [])),
        "email_sent": bool(result.get("email_sent")),
    }
    logger.info("[DIRECT] Pipeline finished for %s", company.company_name)
    return summary
