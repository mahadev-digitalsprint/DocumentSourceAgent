"""
M6 — LLM Metadata Extraction Agent
=====================================
Extracts 15 structured fields from each PDF document using Azure OpenAI gpt-4.1.
Routes financial documents through a financial prompt and non-financial documents
through a non-financial prompt for maximum accuracy.

Financial prompt extracts:
  company_name, filing_date, period_end_date, document_category, document_type,
  fiscal_year, fiscal_quarter, currency, revenue, net_profit, ebitda,
  eps, headline, language, audit_status, is_preliminary, financial_notes

Non-financial prompt extracts:
  company_name, filing_date, document_category, document_type,
  headline, language, key_topics, regulatory_body, compliance_period,
  document_scope, target_audience, key_findings, certifications
"""
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from app.config import get_settings
from app.database import SessionLocal
from app.models import DocumentRegistry, MetadataRecord
from app.workflow.state import PipelineState

logger = logging.getLogger(__name__)
settings = get_settings()

# ── LLM Prompts ───────────────────────────────────────────────────────────────

FINANCIAL_SYSTEM_PROMPT = """You are a specialist financial document analyst.
Your task is to extract structured metadata from financial documents (annual reports,
quarterly results, earnings releases, investor presentations, financial statements, etc.)

EXTRACTION RULES:
- Extract ONLY what is explicitly stated. Do NOT guess or infer.
- For dates use ISO format: YYYY-MM-DD. If only year known: YYYY-01-01.
- For financial figures: extract as plain numbers (no commas, no currency symbol).
- currency: 3-letter ISO code (INR, USD, GBP, etc.)
- audit_status: "Audited", "Unaudited", or "Unknown"
- is_preliminary: true if labelled preliminary/unaudited/subject to audit
- If a field cannot be determined, return null.

Return ONLY valid JSON. No markdown, no explanation, no preamble."""

FINANCIAL_USER_TEMPLATE = """Extract the following fields from this financial document.

DOCUMENT TEXT (first 4000 characters):
{text}

Return a JSON object with EXACTLY these keys:
{{
  "company_name": "string or null",
  "filing_date": "YYYY-MM-DD or null",
  "period_end_date": "YYYY-MM-DD or null",
  "document_category": "FINANCIAL",
  "document_type": "one of: ANNUAL_REPORT|QUARTERLY_RESULTS|HALF_YEAR_RESULTS|EARNINGS_RELEASE|INVESTOR_PRESENTATION|FINANCIAL_STATEMENT|IPO_PROSPECTUS|RIGHTS_ISSUE|DIVIDEND_NOTICE|CONCALL_TRANSCRIPT",
  "fiscal_year": "string like FY2024 or null",
  "fiscal_quarter": "Q1|Q2|Q3|Q4 or null",
  "currency": "INR|USD|GBP|EUR or null",
  "revenue": null or number,
  "net_profit": null or number,
  "ebitda": null or number,
  "eps": null or number,
  "headline": "one sentence summary max 20 words",
  "language": "English|Hindi|Tamil|etc",
  "audit_status": "Audited|Unaudited|Unknown",
  "is_preliminary": true or false,
  "financial_notes": "any key accounting policy or restatement note, max 50 words or null"
}}"""

NON_FINANCIAL_SYSTEM_PROMPT = """You are a specialist corporate document analyst.
Your task is to extract structured metadata from non-financial corporate documents
(ESG reports, governance reports, press releases, regulatory filings, HR reports, etc.)

EXTRACTION RULES:
- Extract ONLY what is explicitly stated. Do NOT guess or infer.
- For dates use ISO format: YYYY-MM-DD.
- If a field cannot be determined, return null.

Return ONLY valid JSON. No markdown, no explanation, no preamble."""

NON_FINANCIAL_USER_TEMPLATE = """Extract the following fields from this corporate document.

DOCUMENT TEXT (first 4000 characters):
{text}

Return a JSON object with EXACTLY these keys:
{{
  "company_name": "string or null",
  "filing_date": "YYYY-MM-DD or null",
  "document_category": "NON_FINANCIAL",
  "document_type": "one of: ESG_REPORT|CORPORATE_GOVERNANCE|PRESS_RELEASE|REGULATORY_FILING|LEGAL_DOCUMENT|HR_PEOPLE|PRODUCT_BROCHURE|OTHER",
  "headline": "one sentence summary max 20 words",
  "language": "English|Hindi|Tamil|etc",
  "key_topics": ["topic1","topic2","topic3"],
  "regulatory_body": "SEBI|RBI|MCA|NSE|BSE|Other or null",
  "compliance_period": "string like FY2024 or null",
  "document_scope": "global|india|regional or null",
  "target_audience": "investors|regulators|employees|public or null",
  "key_findings": "2-3 sentence summary of key findings or null",
  "certifications": ["ISO 14001","GRI","etc"] or []
}}"""


# ── Main agent function ───────────────────────────────────────────────────────

def extract_agent(state: PipelineState) -> dict:
    """LangGraph node — extract metadata from all downloaded documents."""
    db = SessionLocal()
    extracted_count = 0
    try:
        for doc_info in state.get("downloaded_docs", []):
            doc_id = doc_info.get("doc_id")
            full_text = doc_info.get("full_text", "")
            if not doc_id or not full_text:
                continue

            doc = db.get(DocumentRegistry, doc_id)
            if not doc:
                continue

            # Determine category from classify_agent result
            doc_type_field = doc.doc_type or ""
            is_financial = doc_type_field.startswith("FINANCIAL")

            metadata = _extract_with_llm(full_text, is_financial=is_financial) or {}
            metadata = _merge_fallback_metadata(doc, metadata, full_text, is_financial=is_financial)

            _upsert_metadata(db, doc_id, metadata)
            doc.metadata_extracted = True
            db.commit()
            extracted_count += 1
            logger.info(f"[M6-EXTRACT] doc_id={doc_id} → {metadata.get('document_type','?')}")

    finally:
        db.close()

    logger.info(f"[M6-EXTRACT] Total extracted: {extracted_count}")
    return {}


# ── LLM call ─────────────────────────────────────────────────────────────────

def _extract_with_llm(full_text: str, is_financial: bool) -> Optional[Dict[str, Any]]:
    """Call Azure OpenAI with the appropriate prompt. Retries on failure."""
    text_snippet = full_text[:4000]

    if is_financial:
        system_prompt = FINANCIAL_SYSTEM_PROMPT
        user_prompt = FINANCIAL_USER_TEMPLATE.format(text=text_snippet)
    else:
        system_prompt = NON_FINANCIAL_SYSTEM_PROMPT
        user_prompt = NON_FINANCIAL_USER_TEMPLATE.format(text=text_snippet)

    for attempt in range(3):
        try:
            result = _call_azure(system_prompt, user_prompt)
            if result:
                return result
        except Exception as e:
            logger.warning(f"[M6-EXTRACT] Attempt {attempt+1} failed: {e}")

    return None


def _call_azure(system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
    if not settings.azure_openai_endpoint or not settings.azure_openai_key:
        return _call_openai(system_prompt, user_prompt)

    from openai import AzureOpenAI
    client = AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_key,
        api_version=settings.azure_openai_api_version,
    )
    response = client.chat.completions.create(
        model=settings.azure_openai_deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=1000,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    return _parse_json(raw)


def _call_openai(system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
    if not settings.openai_api_key:
        return None
    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=1000,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    return _parse_json(raw)


def _parse_json(raw: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return None


def _merge_fallback_metadata(doc: DocumentRegistry, data: Dict[str, Any], full_text: str, is_financial: bool) -> Dict[str, Any]:
    """
    Fill missing metadata fields from deterministic sources when LLM is partial/unavailable.
    """
    merged = dict(data or {})
    text = full_text or ""
    snippet = text[:4000]

    if not merged.get("document_category"):
        merged["document_category"] = "FINANCIAL" if is_financial else "NON_FINANCIAL"
    if not merged.get("document_type"):
        merged["document_type"] = (doc.doc_type or "UNKNOWN|OTHER").split("|")[-1]
    if not merged.get("language"):
        merged["language"] = doc.language if doc.language and doc.language != "Unknown" else "English"
    if not merged.get("headline"):
        merged["headline"] = _derive_headline(doc, snippet)
    if not merged.get("filing_date"):
        merged["filing_date"] = _derive_date(snippet, doc.document_url)
    if merged.get("document_category") == "NON_FINANCIAL":
        merged.setdefault("key_topics", _derive_topics(snippet))
        merged.setdefault("certifications", [])
    if merged.get("document_category") == "FINANCIAL":
        merged.setdefault("audit_status", "Unknown")
        merged.setdefault("is_preliminary", False)

    return merged


def _derive_headline(doc: DocumentRegistry, text: str) -> str:
    first_line = ""
    for line in text.splitlines():
        cleaned = line.strip()
        if len(cleaned) > 15:
            first_line = cleaned
            break
    if first_line:
        return first_line[:120]

    path = urlparse(doc.document_url or "").path
    file_name = (path.split("/")[-1] or "Document").replace(".pdf", "")
    file_name = re.sub(r"[_\-]+", " ", file_name).strip()
    return file_name[:120] or "Document metadata extracted"


def _derive_date(text: str, url: str) -> Optional[str]:
    # 2024-03-31 / 2024/03/31
    m = re.search(r"\b(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # 31/03/2024 or 31-03-2024
    m = re.search(r"\b(0[1-9]|[12]\d|3[01])[-/](0[1-9]|1[0-2])[-/](20\d{2})\b", text)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

    # fallback to year in URL/text
    m = re.search(r"\b(20\d{2})\b", f"{url} {text[:500]}")
    if m:
        return f"{m.group(1)}-01-01"
    return None


def _derive_topics(text: str):
    topic_bank = [
        "sustainability", "governance", "compliance", "regulatory", "board", "risk",
        "employee", "diversity", "climate", "esg", "product", "legal",
    ]
    lower = text.lower()
    topics = [t for t in topic_bank if t in lower]
    return topics[:5]


# ── DB upsert ─────────────────────────────────────────────────────────────────

def _upsert_metadata(db, doc_id: int, data: Dict[str, Any]):
    rec = db.query(MetadataRecord).filter(MetadataRecord.document_id == doc_id).first()
    if not rec:
        rec = MetadataRecord(document_id=doc_id)
        db.add(rec)

    # Map LLM output to ORM fields
    rec.headline          = data.get("headline")
    rec.filing_date       = data.get("filing_date")
    rec.document_type     = data.get("document_type")
    rec.language          = data.get("language")
    rec.period_end_date   = data.get("period_end_date")
    rec.income_statement  = bool(data.get("revenue") or data.get("net_profit"))
    rec.preliminary_document = bool(data.get("is_preliminary", False))
    rec.audit_flag        = (data.get("audit_status") == "Audited")
    rec.note_flag         = bool(data.get("financial_notes") or data.get("key_findings"))
    rec.filing_data_source = data.get("regulatory_body") or "Company IR Site"
    rec.raw_llm_response  = data
    db.commit()
