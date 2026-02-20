"""
M5 — PDF Parser / OCR Agent
Extracts full text from each PDF.

Pipeline:
  1. PyMuPDF   — fastest, native text layer
  2. pdfplumber — fallback for complex layouts
  3. Tesseract OCR — scanned/image PDFs (detected if text < 300 chars)

Also:
  - Stores page count
  - Detects if document is scanned (is_scanned flag)
  - Caches first_page_text for fast classification
  - Language detection via langdetect
"""
import logging
from typing import Optional
from app.workflow.state import PipelineState
from app.database import SessionLocal
from app.models import DocumentRegistry

logger = logging.getLogger(__name__)

MIN_TEXT_CHARS = 300    # below this → suspect scanned PDF
MAX_CHARS = 30_000      # send at most this many chars to LLM (~8k tokens)
OCR_DPI = 300
OCR_MAX_PAGES = 10


def parse_agent(state: PipelineState) -> dict:
    """LangGraph node — extract text from every downloaded PDF."""
    db = SessionLocal()
    try:
        for doc_info in state.get("downloaded_docs", []):
            if doc_info.get("status") == "UNCHANGED" or not doc_info.get("local_path"):
                continue
            doc: Optional[DocumentRegistry] = db.get(DocumentRegistry, doc_info.get("doc_id"))
            if not doc or not doc.local_path:
                continue

            result = extract_text(doc.local_path)

            doc.first_page_text = result["first_page_text"]
            doc.page_count = result["page_count"]
            doc.is_scanned = result["is_scanned"]
            doc.language = result["language"]
            # Store full text in the doc_info dict for the extract step
            doc_info["full_text"] = result["full_text"]
            logger.info(
                f"[M5-PARSE] {doc.document_url} — "
                f"{result['page_count']}p, scanned={result['is_scanned']}, "
                f"lang={result['language']}, chars={len(result['full_text'])}"
            )
        db.commit()
    finally:
        db.close()

    return {"downloaded_docs": state.get("downloaded_docs", [])}


def extract_text(file_path: str) -> dict:
    """
    Returns {full_text, first_page_text, page_count, is_scanned, language}
    """
    result = {"full_text": "", "first_page_text": "", "page_count": 0, "is_scanned": False, "language": "Unknown"}

    # Try PyMuPDF
    text, page_count, first_page_text = _pymupdf(file_path)

    # If sparse text → try pdfplumber
    if len(text.strip()) < MIN_TEXT_CHARS:
        text2, pc2, fp2 = _pdfplumber(file_path)
        if len(text2.strip()) > len(text.strip()):
            text, page_count, first_page_text = text2, pc2, fp2

    # Still sparse → OCR
    if len(text.strip()) < MIN_TEXT_CHARS:
        logger.info(f"[M5-PARSE] Scanned PDF detected, running OCR: {file_path}")
        text = _tesseract(file_path)
        result["is_scanned"] = True

    # Language detection
    result["language"] = _detect_language(text)
    result["full_text"] = text[:MAX_CHARS]
    result["first_page_text"] = first_page_text[:3000]
    result["page_count"] = page_count
    return result


def _pymupdf(path: str):
    try:
        import fitz
        doc = fitz.open(path)
        pages = []
        for i, page in enumerate(doc):
            pages.append(page.get_text())
        doc.close()
        first = pages[0] if pages else ""
        return "\n".join(pages), len(pages), first
    except Exception as e:
        logger.warning(f"[M5-PARSE][PyMuPDF] {path}: {e}")
        return "", 0, ""


def _pdfplumber(path: str):
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages.append(t)
        first = pages[0] if pages else ""
        return "\n".join(pages), len(pages), first
    except Exception as e:
        logger.warning(f"[M5-PARSE][pdfplumber] {path}: {e}")
        return "", 0, ""


def _tesseract(path: str) -> str:
    try:
        from pdf2image import convert_from_path
        import pytesseract
        images = convert_from_path(path, dpi=OCR_DPI, first_page=1, last_page=OCR_MAX_PAGES)
        return "\n".join(pytesseract.image_to_string(img) for img in images)
    except Exception as e:
        logger.error(f"[M5-PARSE][Tesseract] {path}: {e}")
        return ""


def _detect_language(text: str) -> str:
    try:
        from langdetect import detect
        lang = detect(text[:5000])
        return lang
    except Exception:
        return "Unknown"
