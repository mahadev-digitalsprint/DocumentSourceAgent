"""
M4 — Document Classification Agent
Classifies each PDF into a canonical document type using 3-tier heuristics.

Tier 1: Filename regex
Tier 2: URL path keywords
Tier 3: First-page text patterns
Tier 4: LLM fallback (only for ambiguous documents)

Output types: Annual Report | Quarterly Report | Financial Statement | ESG Report | Unknown
"""
import re
import logging
from typing import Optional

from app.workflow.state import PipelineState
from app.database import SessionLocal
from app.models import DocumentRegistry

logger = logging.getLogger(__name__)

# ── Regex patterns ─────────────────────────────────────────────────────────
_ANNUAL = [r"annual.?report", r"\bar\s?20\d{2}\b", r"annual.?results",
           r"year.?end", r"full.?year", r"fy\d{2,4}", r"annual.?accounts"]
_QUARTERLY = [r"q[1-4].?20\d{2}", r"quarter(ly)?", r"qr\d{2,4}",
              r"q[1-4]fy", r"half.?year", r"interim", r"six.?month"]
_FINANCIAL = [r"financial.?statement", r"balance.?sheet", r"fs\d{2,4}",
              r"financial.?result", r"standalone", r"consolidated.?accounts"]
_ESG = [r"esg", r"sustainab", r"csr.?report", r"environment", r"social.?governance"]

# ── URL path keywords ──────────────────────────────────────────────────────
_URL_ANNUAL = ["/annual", "/ar/", "/annual-report", "/full-year"]
_URL_QUARTERLY = ["/quarterly", "/qr/", "/interim", "/half-year", "/q1", "/q2", "/q3", "/q4"]
_URL_FINANCIAL = ["/financial-statement", "/accounts", "/financial-result"]
_URL_ESG = ["/esg", "/sustainability", "/csr"]

# ── First-page text keywords ───────────────────────────────────────────────
_TEXT_ANNUAL = ["annual report", "to our shareholders", "year ended", "full year"]
_TEXT_QUARTERLY = ["quarter ended", "first quarter", "second quarter", "third quarter",
                   "fourth quarter", "q1 ", "q2 ", "q3 ", "q4 ", "nine months"]
_TEXT_FINANCIAL = ["statement of financial position", "balance sheet", "financial statements",
                   "profit and loss", "income statement"]
_TEXT_ESG = ["esg report", "sustainability report", "corporate responsibility"]


def classify_agent(state: PipelineState) -> dict:
    """LangGraph node — classifies doc_type for every downloaded document."""
    db = SessionLocal()
    try:
        for doc_info in state.get("downloaded_docs", []):
            if doc_info.get("status") == "UNCHANGED":
                continue
            doc: Optional[DocumentRegistry] = db.query(DocumentRegistry).get(doc_info.get("doc_id"))
            if not doc:
                continue

            doc_type = classify_doc(
                filename=doc.local_path.split("/")[-1] if doc.local_path else "",
                url=doc.document_url,
                first_page_text=doc.first_page_text or "",
            )
            doc.doc_type = doc_type
            logger.info(f"[M4-CLASSIFY] {doc_type}: {doc.document_url}")
        db.commit()
    finally:
        db.close()

    return {}


def classify_doc(filename: str = "", url: str = "", first_page_text: str = "") -> str:
    """
    Pure function — classifies a document.
    Returns: Annual Report | Quarterly Report | Financial Statement | ESG Report | Unknown
    """
    fn = filename.lower()
    u = url.lower()
    txt = first_page_text[:3000].lower()

    # ── Tier 1: Filename ──────────────────────────────────────────────────
    if _match(_ESG, fn):     return "ESG Report"
    if _match(_ANNUAL, fn):  return "Annual Report"
    if _match(_QUARTERLY, fn): return "Quarterly Report"
    if _match(_FINANCIAL, fn): return "Financial Statement"

    # ── Tier 2: URL path ──────────────────────────────────────────────────
    if _contains(_URL_ESG, u):       return "ESG Report"
    if _contains(_URL_ANNUAL, u):    return "Annual Report"
    if _contains(_URL_QUARTERLY, u): return "Quarterly Report"
    if _contains(_URL_FINANCIAL, u): return "Financial Statement"

    # ── Tier 3: First-page text ───────────────────────────────────────────
    if txt:
        if _contains(_TEXT_ESG, txt):       return "ESG Report"
        if _contains(_TEXT_ANNUAL, txt):    return "Annual Report"
        if _contains(_TEXT_QUARTERLY, txt): return "Quarterly Report"
        if _contains(_TEXT_FINANCIAL, txt): return "Financial Statement"

    return "Unknown"


def _match(patterns: list, text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _contains(keywords: list, text: str) -> bool:
    return any(k in text for k in keywords)
