"""
M4 — Document Classifier Agent
===============================
Classifies discovered PDFs into a structured two-level taxonomy:

  CATEGORY (top level):
    • FINANCIAL       — directly related to company financial performance
    • NON_FINANCIAL   — corporate, ESG, legal, product, regulatory

  DOC_TYPE (sub-level) — 18 types:

  Financial:
    ANNUAL_REPORT         Full-year financial statements + MD&A
    QUARTERLY_RESULTS     Q1/Q2/Q3/Q4 earnings release / results
    HALF_YEAR_RESULTS     H1/H2 interim financial statements
    EARNINGS_RELEASE      Short-form earnings press release / profit announcement
    INVESTOR_PRESENTATION Investor day / roadshow / analyst deck
    FINANCIAL_STATEMENT   Standalone balance sheet, P&L, cash-flow
    IPO_PROSPECTUS        Initial public offering/DRHP/SEBI prospectus
    RIGHTS_ISSUE          Rights issue / FPO offer document
    DIVIDEND_NOTICE       Dividend declaration / record date notice
    CONCALL_TRANSCRIPT    Earnings conference call transcript/script

  Non-Financial:
    ESG_REPORT            Sustainability / CSR / ESG / BRSR report
    CORPORATE_GOVERNANCE  Board report / governance / compliance filing
    PRESS_RELEASE         News announcement, product launch, M&A news
    REGULATORY_FILING     SEBI, RBI, MCA, Exchange filing (non-financial)
    LEGAL_DOCUMENT        Court filing, arbitration, legal notice
    HR_PEOPLE             HR policy, ESOP, headcount, diversity report
    PRODUCT_BROCHURE      Product / service marketing document
    OTHER                 Unclassified or unknown document type
"""
import logging
import re
from typing import Tuple

from app.config import get_settings
from app.database import SessionLocal
from app.models import DocumentRegistry
from app.workflow.state import PipelineState

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Classification rules ──────────────────────────────────────────────────────
# Each rule: (category, doc_type, [keywords_that_must_appear_in_url_or_filename_or_first_page_text])

RULES = [
    # ── FINANCIAL ──────────────────────────────────────────────────────────────
    ("FINANCIAL", "ANNUAL_REPORT", [
        "annual report", "annual-report", "annualreport", "ar202", "ar-20",
        "yearly report", "full year", "full-year results",
    ]),
    ("FINANCIAL", "QUARTERLY_RESULTS", [
        "quarterly result", "quarter result", "q1 result", "q2 result",
        "q3 result", "q4 result", "q1result", "q2result", "q3result", "q4result",
        "first quarter", "second quarter", "third quarter", "fourth quarter",
        "unaudited result", "qr20", "qtr result",
    ]),
    ("FINANCIAL", "HALF_YEAR_RESULTS", [
        "half year", "half-year", "halfyear", "h1 result", "h2 result",
        "interim result", "six month", "6 month",
    ]),
    ("FINANCIAL", "EARNINGS_RELEASE", [
        "earnings release", "profit announcement", "earnings announcement",
        "net profit", "revenue result", "financial result",
    ]),
    ("FINANCIAL", "INVESTOR_PRESENTATION", [
        "investor presentation", "investor day", "analyst day", "roadshow",
        "analyst presentation", "capital market day", "cmd presentation",
    ]),
    ("FINANCIAL", "FINANCIAL_STATEMENT", [
        "balance sheet", "profit and loss", "p&l", "cash flow statement",
        "standalone financial", "consolidated financial", "financial statement",
    ]),
    ("FINANCIAL", "IPO_PROSPECTUS", [
        "prospectus", "drhp", "rhp", "offer document", "red herring",
        "ipo", "initial public offering",
    ]),
    ("FINANCIAL", "RIGHTS_ISSUE", [
        "rights issue", "rights offer", "fpo", "further public offer",
        "open offer", "buyback",
    ]),
    ("FINANCIAL", "DIVIDEND_NOTICE", [
        "dividend", "record date", "book closure", "interim dividend",
        "final dividend",
    ]),
    ("FINANCIAL", "CONCALL_TRANSCRIPT", [
        "concall", "conference call", "earnings call", "analyst call",
        "q&a transcript", "call transcript",
    ]),

    # ── NON-FINANCIAL ──────────────────────────────────────────────────────────
    ("NON_FINANCIAL", "ESG_REPORT", [
        "esg", "sustainability report", "csr report", "brsr",
        "environmental report", "climate report", "net zero",
        "responsible business",
    ]),
    ("NON_FINANCIAL", "CORPORATE_GOVERNANCE", [
        "corporate governance", "board report", "directors report",
        "governance report", "compliance report", "secretarial audit",
    ]),
    ("NON_FINANCIAL", "PRESS_RELEASE", [
        "press release", "media release", "news release", "announcement",
        "merger", "acquisition", "strategic partnership",
    ]),
    ("NON_FINANCIAL", "REGULATORY_FILING", [
        "sebi", "rbi filing", "mca filing", "exchange filing",
        "stock exchange", "regulatory disclosure", "intimation",
    ]),
    ("NON_FINANCIAL", "LEGAL_DOCUMENT", [
        "court order", "arbitration", "legal notice", "litigation",
        "tribunal", "judgment",
    ]),
    ("NON_FINANCIAL", "HR_PEOPLE", [
        "human resource", "hr policy", "esop", "headcount", "diversity",
        "inclusion", "employee", "people report",
    ]),
    ("NON_FINANCIAL", "PRODUCT_BROCHURE", [
        "product", "brochure", "catalogue", "service offering",
        "solution brief", "datasheet",
    ]),
]


def classify_agent(state: PipelineState) -> dict:
    """LangGraph node — classify each downloaded document."""
    db = SessionLocal()
    try:
        updated = 0
        for doc_info in state.get("downloaded_docs", []):
            doc_id = doc_info.get("doc_id")
            if not doc_id:
                continue

            doc = db.query(DocumentRegistry).get(doc_id)
            if not doc:
                continue

            category, doc_type = _classify(
                url=doc.document_url or "",
                local_path=doc.local_path or "",
                first_page_text=doc.first_page_text or "",
            )

            doc.doc_type = doc_type
            # Store category in doc_type as "CATEGORY|TYPE" for easy filtering
            doc.doc_type = f"{category}|{doc_type}"
            db.commit()
            updated += 1
            logger.info(
                f"[M4-CLASSIFY] doc_id={doc_id} → {category} / {doc_type}"
            )

        return {"downloaded_docs": state.get("downloaded_docs", [])}
    finally:
        db.close()


def _classify(url: str, local_path: str, first_page_text: str) -> Tuple[str, str]:
    """
    Multi-signal classifier using URL path, filename, and first-page text.
    Returns (category, doc_type) tuple.
    """
    # Combine all signals into a single lowercase string for matching
    signals = " ".join([
        url.lower(),
        local_path.lower().split("\\")[-1],
        local_path.lower().split("/")[-1],
        first_page_text.lower()[:3000],   # first 3000 chars of text
    ])

    best_category, best_type, best_score = "NON_FINANCIAL", "OTHER", 0

    for category, doc_type, keywords in RULES:
        score = sum(1 for kw in keywords if kw in signals)
        if score > best_score:
            best_score = score
            best_category = category
            best_type = doc_type

    return best_category, best_type


def get_category_and_type(doc_type_field: str):
    """Parse 'CATEGORY|TYPE' stored value back into (category, type)."""
    if "|" in (doc_type_field or ""):
        parts = doc_type_field.split("|", 1)
        return parts[0], parts[1]
    return "NON_FINANCIAL", doc_type_field or "OTHER"
