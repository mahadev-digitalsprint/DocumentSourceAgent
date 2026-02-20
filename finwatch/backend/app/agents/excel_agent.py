"""
M7 — Excel Writer Agent
Generates a single Excel workbook per company with 5 sheets:
  Sheet 1: Metadata        — 10 LLM-extracted fields per document
  Sheet 2: 24h Changes     — New/Updated/Removed documents in last 24h
  Sheet 3: WebWatch        — Page adds/deletes/updates/new PDF links
  Sheet 4: Error Log       — All failures logged during this run
  Sheet 5: Summary         — Aggregate statistics

Output: downloads/{slug}/metadata_{slug}_{YYYY-MM-DD}.xlsx
"""
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.utils.dataframe import dataframe_to_rows

from app.database import SessionLocal
from app.models import Company, DocumentRegistry, MetadataRecord, ChangeLog, PageChange, ErrorLog
from app.workflow.state import PipelineState

logger = logging.getLogger(__name__)

# Styles
HEADER_BG = "1E3A5F"
ALT_ROW_BG = "F0F4F8"
NEW_COL = "22C55E"
UPDATED_COL = "F59E0B"
DELETED_COL = "EF4444"

thin = Side(border_style="thin", color="CBD5E1")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)


def excel_agent(state: PipelineState) -> dict:
    """LangGraph node — builds the Excel report for one company."""
    db = SessionLocal()
    try:
        company = db.query(Company).get(state["company_id"])
        if not company:
            return {"excel_path": None}

        xlsx_path = _build_excel(db, company, state["base_folder"])
        logger.info(f"[M7-EXCEL] Saved: {xlsx_path}")
        return {"excel_path": xlsx_path}
    except Exception as e:
        logger.error(f"[M7-EXCEL] Failed: {e}")
        return {"excel_path": None}
    finally:
        db.close()


def _build_excel(db, company: Company, base_folder: str) -> str:
    folder = os.path.join(base_folder, company.company_slug)
    Path(folder).mkdir(parents=True, exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    path = os.path.join(folder, f"metadata_{company.company_slug}_{today}.xlsx")

    wb = Workbook()

    _sheet_metadata(wb, db, company, is_first=True)
    _sheet_24h_changes(wb, db, company)
    _sheet_webwatch(wb, db, company)
    _sheet_errors(wb, db, company)
    _sheet_summary(wb, db, company)

    wb.save(path)
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Sheet 1: Metadata
# ─────────────────────────────────────────────────────────────────────────────
def _sheet_metadata(wb: Workbook, db, company: Company, is_first=False):
    ws = wb.active if is_first else wb.create_sheet("Metadata")
    ws.title = "Metadata"

    headers = [
        "Filename", "URL", "Document Type", "Headline",
        "Filing Date", "Period End Date", "Language",
        "Filing Data Source", "Income Statement",
        "Preliminary Doc", "Note Flag", "Audit Flag",
        "Status", "File Size (KB)", "Scanned PDF", "Last Checked",
    ]
    _write_header(ws, headers)

    docs = db.query(DocumentRegistry).filter(DocumentRegistry.company_id == company.id).all()
    for i, doc in enumerate(docs, start=2):
        m: MetadataRecord = doc.metadata
        row = [
            os.path.basename(doc.local_path or ""),
            doc.document_url,
            doc.doc_type,
            m.headline if m else "",
            m.filing_date if m else "",
            m.period_end_date if m else "",
            doc.language or "",
            m.filing_data_source if m else "",
            _bool(m.income_statement if m else None),
            _bool(m.preliminary_document if m else None),
            _bool(m.note_flag if m else None),
            _bool(m.audit_flag if m else None),
            doc.status,
            round(doc.file_size_bytes / 1024, 1) if doc.file_size_bytes else "",
            "Yes" if doc.is_scanned else "No",
            str(doc.last_checked)[:19] if doc.last_checked else "",
        ]
        ws.append(row)
        # Colour status cell
        status_cell = ws.cell(row=i, column=headers.index("Status") + 1)
        colour_map = {"NEW": NEW_COL, "UPDATED": UPDATED_COL, "FAILED": DELETED_COL}
        if doc.status in colour_map:
            status_cell.fill = PatternFill("solid", fgColor=colour_map[doc.status])

        if i % 2 == 0:
            _apply_alt_row(ws, i, len(headers))

    _auto_width(ws)
    ws.freeze_panes = "A2"


# ─────────────────────────────────────────────────────────────────────────────
# Sheet 2: 24h Changes
# ─────────────────────────────────────────────────────────────────────────────
def _sheet_24h_changes(wb: Workbook, db, company: Company):
    ws = wb.create_sheet("24h Changes")
    cutoff = datetime.utcnow() - timedelta(hours=24)

    docs = db.query(DocumentRegistry).filter(DocumentRegistry.company_id == company.id).all()
    doc_ids = [d.id for d in docs]
    changes = (
        db.query(ChangeLog)
        .filter(ChangeLog.document_id.in_(doc_ids), ChangeLog.detected_at >= cutoff)
        .order_by(ChangeLog.detected_at.desc())
        .all()
    )

    headers = ["Detected At", "Change Type", "Document Type", "Filename", "URL", "Old Hash", "New Hash"]
    _write_header(ws, headers)

    for i, c in enumerate(changes, start=2):
        doc = c.document
        colour_map = {"NEW": NEW_COL, "UPDATED": UPDATED_COL, "REMOVED": DELETED_COL}
        row = [
            str(c.detected_at)[:19],
            c.change_type,
            doc.doc_type if doc else "",
            os.path.basename(doc.local_path or "") if doc else "",
            doc.document_url if doc else "",
            (c.old_hash or "")[:16],
            (c.new_hash or "")[:16],
        ]
        ws.append(row)
        ct_cell = ws.cell(row=i, column=2)
        if c.change_type in colour_map:
            ct_cell.fill = PatternFill("solid", fgColor=colour_map[c.change_type])

    if not changes:
        ws.append(["No document changes in the last 24 hours"])

    _auto_width(ws)
    ws.freeze_panes = "A2"


# ─────────────────────────────────────────────────────────────────────────────
# Sheet 3: WebWatch
# ─────────────────────────────────────────────────────────────────────────────
def _sheet_webwatch(wb: Workbook, db, company: Company):
    ws = wb.create_sheet("WebWatch")
    cutoff = datetime.utcnow() - timedelta(hours=24)

    page_changes = (
        db.query(PageChange)
        .filter(PageChange.company_id == company.id, PageChange.detected_at >= cutoff)
        .order_by(PageChange.detected_at.desc())
        .all()
    )

    headers = ["Detected At", "Change Type", "Page URL", "Diff Summary", "New PDFs Linked"]
    _write_header(ws, headers)

    colour_map = {
        "PAGE_ADDED": NEW_COL,
        "PAGE_DELETED": DELETED_COL,
        "CONTENT_CHANGED": UPDATED_COL,
        "NEW_DOC_LINKED": "3B82F6",
    }

    for i, p in enumerate(page_changes, start=2):
        new_pdfs = ", ".join(p.new_pdf_urls or [])[:200]
        ws.append([
            str(p.detected_at)[:19],
            p.change_type.replace("_", " "),
            p.page_url,
            (p.diff_summary or "")[:300],
            new_pdfs,
        ])
        ct_cell = ws.cell(row=i, column=2)
        if p.change_type in colour_map:
            ct_cell.fill = PatternFill("solid", fgColor=colour_map[p.change_type])

    if not page_changes:
        ws.append(["No page changes in the last 24 hours"])

    _auto_width(ws)
    ws.freeze_panes = "A2"


# ─────────────────────────────────────────────────────────────────────────────
# Sheet 4: Error Log
# ─────────────────────────────────────────────────────────────────────────────
def _sheet_errors(wb: Workbook, db, company: Company):
    ws = wb.create_sheet("Error Log")
    errors = db.query(ErrorLog).filter(ErrorLog.company_id == company.id).order_by(ErrorLog.created_at.desc()).all()
    _write_header(ws, ["Timestamp", "Step", "Error Type", "Document URL", "Message"])
    for e in errors:
        ws.append([str(e.created_at)[:19], e.step, e.error_type, e.document_url, e.error_message])
    if not errors:
        ws.append(["No errors logged"])
    _auto_width(ws)


# ─────────────────────────────────────────────────────────────────────────────
# Sheet 5: Summary
# ─────────────────────────────────────────────────────────────────────────────
def _sheet_summary(wb: Workbook, db, company: Company):
    ws = wb.create_sheet("Summary")
    cutoff = datetime.utcnow() - timedelta(hours=24)
    docs = db.query(DocumentRegistry).filter(DocumentRegistry.company_id == company.id).all()
    doc_ids = [d.id for d in docs]
    changes_24h = db.query(ChangeLog).filter(
        ChangeLog.document_id.in_(doc_ids), ChangeLog.detected_at >= cutoff
    ).all()
    page_changes_24h = db.query(PageChange).filter(
        PageChange.company_id == company.id, PageChange.detected_at >= cutoff
    ).all()

    _write_header(ws, ["Metric", "Value"])
    rows = [
        ["Company", company.company_name],
        ["Website", company.website_url],
        ["Report Date", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")],
        ["Total Documents", len(docs)],
        ["Annual Reports", sum(1 for d in docs if d.doc_type == "Annual Report")],
        ["Quarterly Reports", sum(1 for d in docs if d.doc_type == "Quarterly Report")],
        ["Financial Statements", sum(1 for d in docs if d.doc_type == "Financial Statement")],
        ["ESG Reports", sum(1 for d in docs if d.doc_type == "ESG Report")],
        ["Metadata Extracted", sum(1 for d in docs if d.metadata_extracted)],
        ["Scanned PDFs", sum(1 for d in docs if d.is_scanned)],
        ["Failed Downloads", sum(1 for d in docs if d.status == "FAILED")],
        ["--- 24h Changes ---", ""],
        ["New Documents (24h)", sum(1 for c in changes_24h if c.change_type == "NEW")],
        ["Updated Documents (24h)", sum(1 for c in changes_24h if c.change_type == "UPDATED")],
        ["Pages Added (24h)", sum(1 for p in page_changes_24h if p.change_type == "PAGE_ADDED")],
        ["Pages Deleted (24h)", sum(1 for p in page_changes_24h if p.change_type == "PAGE_DELETED")],
        ["Page Content Changes (24h)", sum(1 for p in page_changes_24h if p.change_type == "CONTENT_CHANGED")],
        ["New PDF Links (24h)", sum(1 for p in page_changes_24h if p.change_type == "NEW_DOC_LINKED")],
    ]
    for row in rows:
        ws.append(row)

    _auto_width(ws)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _write_header(ws, headers: list):
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor=HEADER_BG)
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER
    ws.row_dimensions[1].height = 20


def _apply_alt_row(ws, row_idx: int, col_count: int):
    for col in range(1, col_count + 1):
        ws.cell(row=row_idx, column=col).fill = PatternFill("solid", fgColor=ALT_ROW_BG)


def _auto_width(ws):
    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=10)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 3, 70)


def _bool(val) -> str:
    if val is None: return ""
    return "TRUE" if val else "FALSE"
