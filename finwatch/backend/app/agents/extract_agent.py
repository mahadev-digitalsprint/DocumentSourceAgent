"""
M6 — LLM Metadata Extraction Agent
Extracts 10 canonical fields from each PDF's text.

Provider chain:
  1. Azure OpenAI GPT-4o  (primary)
  2. OpenAI gpt-4o-mini   (fallback)

Enforces: JSON response_format, temperature=0, 2 retries per provider.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.config import get_settings
from app.workflow.state import PipelineState
from app.database import SessionLocal
from app.models import DocumentRegistry, MetadataRecord, ErrorLog

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """\
You are a financial document metadata extraction specialist.
You will receive raw text from a financial PDF document.
Extract EXACTLY these 10 fields and return a valid JSON object ONLY — no markdown, no explanation.

Fields and rules:
1. "Headline": string — the main title/headline of the document. null if not found.
2. "Filing Date": YYYY-MM-DD string — the date the document was published/filed. null if not found.
3. "Filing Data Source": string — the source URL or publisher. Use the provided URL if not found in text.
4. "Language": string — ISO 639-1 language code (en, hi, zh, etc.) or full name.
5. "Period End Date": YYYY-MM-DD — the financial period this document covers through.
6. "Document Type": one of ["Annual Report","Quarterly Report","Financial Statement","ESG Report","Unknown"]
7. "Income Statement": true | false — does the doc contain an income/P&L statement?
8. "Preliminary Document": true | false — is this preliminary/unaudited?
9. "Note Flag": true | false — are there significant notes to financial statements?
10. "Audit Flag": true | false — has this been audited by an external auditor?

RULES:
- Return ONLY valid JSON. No backticks, no explanation text.
- Dates MUST be YYYY-MM-DD or null.
- Booleans MUST be literal true or false.
- Never hallucinate. Set to null if not explicitly stated.
"""


def extract_agent(state: PipelineState) -> dict:
    """LangGraph node — LLM metadata extraction for each new/updated doc."""
    db = SessionLocal()
    llm = _init_llm()

    try:
        for doc_info in state.get("downloaded_docs", []):
            if doc_info.get("status") == "UNCHANGED":
                continue
            doc: Optional[DocumentRegistry] = db.query(DocumentRegistry).get(doc_info.get("doc_id"))
            if not doc:
                continue

            full_text = doc_info.get("full_text", "")
            if not full_text and doc.first_page_text:
                full_text = doc.first_page_text  # fallback to cached text

            if not full_text:
                logger.warning(f"[M6-EXTRACT] No text available for doc {doc.id}, skipping")
                continue

            meta = _extract(llm, full_text, doc.document_url)

            # Upsert MetadataRecord
            existing = doc.metadata
            if existing:
                db.delete(existing)
                db.flush()

            record = MetadataRecord(
                document_id=doc.id,
                headline=meta.get("Headline"),
                filing_date=meta.get("Filing Date"),
                filing_data_source=meta.get("Filing Data Source") or doc.document_url,
                language=meta.get("Language") or doc.language,
                period_end_date=meta.get("Period End Date"),
                document_type=meta.get("Document Type") or doc.doc_type,
                income_statement=meta.get("Income Statement"),
                preliminary_document=meta.get("Preliminary Document"),
                note_flag=meta.get("Note Flag"),
                audit_flag=meta.get("Audit Flag"),
                raw_llm_response=meta,
            )
            db.add(record)
            doc.metadata_extracted = bool(meta)
            db.commit()
            logger.info(f"[M6-EXTRACT] Extracted metadata for doc {doc.id}: {meta.get('Headline', 'N/A')}")

    except Exception as e:
        logger.error(f"[M6-EXTRACT] Fatal error: {e}")
    finally:
        db.close()

    return {}


def _extract(llm_clients, text: str, url: str) -> Dict[str, Any]:
    """Try each LLM provider in order. Returns metadata dict."""
    payload = f"Document URL: {url}\n\n---\n\n{text[:28000]}"

    for client, model in llm_clients:
        for attempt in range(2):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": payload},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=1000,
                )
                raw = resp.choices[0].message.content
                result = json.loads(raw)
                # Validate known keys
                allowed = {
                    "Headline", "Filing Date", "Filing Data Source", "Language",
                    "Period End Date", "Document Type", "Income Statement",
                    "Preliminary Document", "Note Flag", "Audit Flag",
                }
                return {k: v for k, v in result.items() if k in allowed}
            except json.JSONDecodeError:
                logger.warning(f"[M6-EXTRACT][{model}] Invalid JSON (attempt {attempt+1}), retrying…")
            except Exception as e:
                logger.error(f"[M6-EXTRACT][{model}] API error: {e}")
                break  # try next provider

    logger.error("[M6-EXTRACT] All LLM providers failed")
    return {}


def _init_llm():
    """Returns list of (client, model) tuples to try in order."""
    clients = []

    # Azure OpenAI
    if settings.azure_openai_endpoint and settings.azure_openai_key:
        try:
            from openai import AzureOpenAI
            clients.append((
                AzureOpenAI(
                    api_key=settings.azure_openai_key,
                    azure_endpoint=settings.azure_openai_endpoint,
                    api_version=settings.azure_openai_api_version,
                ),
                settings.azure_openai_deployment,
            ))
        except Exception as e:
            logger.warning(f"[M6-EXTRACT] Azure init failed: {e}")

    # OpenAI fallback
    if settings.openai_api_key:
        try:
            from openai import OpenAI
            clients.append((OpenAI(api_key=settings.openai_api_key), "gpt-4o-mini"))
        except Exception as e:
            logger.warning(f"[M6-EXTRACT] OpenAI init failed: {e}")

    return clients
