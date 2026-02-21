"""Rule-based document classifier with confidence scoring."""
from __future__ import annotations

import logging
from typing import List, Tuple

from app.config import get_settings
from app.database import SessionLocal
from app.models import Company, DocumentRegistry
from app.services.file_organizer import move_to_classified_folder
from app.workflow.state import PipelineState

logger = logging.getLogger(__name__)
settings = get_settings()

# (category, doc_type, keyword list)
RULES = [
    ("FINANCIAL", "ANNUAL_REPORT", ["annual report", "annual-report", "annualreport", "full year", "full-year"]),
    ("FINANCIAL", "QUARTERLY_RESULTS", ["quarterly result", "quarter result", "q1 result", "q2 result", "q3 result", "q4 result", "unaudited result"]),
    ("FINANCIAL", "HALF_YEAR_RESULTS", ["half year", "half-year", "interim result", "six month", "6 month"]),
    ("FINANCIAL", "EARNINGS_RELEASE", ["earnings release", "profit announcement", "earnings announcement"]),
    ("FINANCIAL", "INVESTOR_PRESENTATION", ["investor presentation", "investor day", "analyst presentation", "roadshow"]),
    ("FINANCIAL", "FINANCIAL_STATEMENT", ["balance sheet", "profit and loss", "p&l", "cash flow statement", "financial statement"]),
    ("FINANCIAL", "IPO_PROSPECTUS", ["prospectus", "drhp", "rhp", "red herring", "ipo"]),
    ("FINANCIAL", "RIGHTS_ISSUE", ["rights issue", "rights offer", "fpo", "open offer", "buyback"]),
    ("FINANCIAL", "DIVIDEND_NOTICE", ["dividend", "record date", "book closure", "interim dividend", "final dividend"]),
    ("FINANCIAL", "CONCALL_TRANSCRIPT", ["concall", "conference call", "earnings call", "analyst call", "call transcript"]),
    ("NON_FINANCIAL", "ESG_REPORT", ["esg", "sustainability report", "csr report", "brsr", "climate report"]),
    ("NON_FINANCIAL", "CORPORATE_GOVERNANCE", ["corporate governance", "board report", "directors report", "governance report"]),
    ("NON_FINANCIAL", "PRESS_RELEASE", ["press release", "media release", "news release", "announcement", "merger", "acquisition"]),
    ("NON_FINANCIAL", "REGULATORY_FILING", ["sebi", "rbi filing", "mca filing", "exchange filing", "regulatory disclosure"]),
    ("NON_FINANCIAL", "LEGAL_DOCUMENT", ["court order", "arbitration", "legal notice", "litigation", "judgment"]),
    ("NON_FINANCIAL", "HR_PEOPLE", ["human resource", "hr policy", "esop", "headcount", "diversity", "employee"]),
    ("NON_FINANCIAL", "PRODUCT_BROCHURE", ["product", "brochure", "catalogue", "service offering", "datasheet"]),
]


def classify_agent(state: PipelineState) -> dict:
    """Classify downloaded documents and persist confidence/review flags."""
    db = SessionLocal()
    try:
        for doc_info in state.get("downloaded_docs", []):
            doc_id = doc_info.get("doc_id")
            if not doc_id:
                continue
            doc = db.get(DocumentRegistry, doc_id)
            if not doc:
                continue

            category, doc_type, confidence, reasons = _classify(
                url=doc.document_url or "",
                local_path=doc.local_path or "",
                first_page_text=doc.first_page_text or "",
            )

            doc.doc_type = f"{category}|{doc_type}"
            doc.classifier_confidence = confidence
            doc.classifier_version = "rule_v2"
            doc.needs_review = confidence < 0.6 or doc_type == "OTHER"

            company = db.get(Company, doc.company_id)
            if company and doc.local_path:
                shared_path_count = (
                    db.query(DocumentRegistry)
                    .filter(
                        DocumentRegistry.id != doc.id,
                        DocumentRegistry.local_path == doc.local_path,
                    )
                    .count()
                )
                doc.local_path = move_to_classified_folder(
                    local_path=doc.local_path,
                    company_slug=company.company_slug,
                    doc_type_field=doc.doc_type,
                    default_base=settings.base_download_path,
                    copy_mode=shared_path_count > 0,
                )
            db.commit()

            logger.info(
                "[M4-CLASSIFY] doc_id=%s -> %s/%s confidence=%.2f needs_review=%s reasons=%s",
                doc_id,
                category,
                doc_type,
                confidence,
                doc.needs_review,
                ",".join(reasons[:3]) if reasons else "none",
            )

        return {"downloaded_docs": state.get("downloaded_docs", [])}
    finally:
        db.close()


def _classify(url: str, local_path: str, first_page_text: str) -> Tuple[str, str, float, List[str]]:
    signals = " ".join(
        [
            url.lower(),
            local_path.lower().split("\\")[-1],
            local_path.lower().split("/")[-1],
            first_page_text.lower()[:3000],
        ]
    )

    best_category, best_type = "NON_FINANCIAL", "OTHER"
    best_score = 0
    second_score = 0
    best_reasons: List[str] = []

    for category, doc_type, keywords in RULES:
        matched = [kw for kw in keywords if kw in signals]
        score = len(matched)
        if score > best_score:
            second_score = best_score
            best_score = score
            best_category = category
            best_type = doc_type
            best_reasons = matched[:6]
        elif score > second_score:
            second_score = score

    confidence = _confidence(best_score, second_score, best_type)
    return best_category, best_type, confidence, best_reasons


def _confidence(best_score: int, second_score: int, best_type: str) -> float:
    if best_score <= 0:
        return 0.2
    base = min(0.95, 0.3 + (0.1 * best_score))
    if second_score == 0:
        base += 0.1
    else:
        gap = max(0.0, (best_score - second_score) / max(1.0, float(best_score)))
        base += 0.2 * gap
    if best_type == "OTHER":
        base = min(base, 0.5)
    return max(0.05, min(0.99, base))


def get_category_and_type(doc_type_field: str) -> Tuple[str, str]:
    if "|" in (doc_type_field or ""):
        parts = doc_type_field.split("|", 1)
        return parts[0], parts[1]
    return "NON_FINANCIAL", doc_type_field or "OTHER"
