"""
M8 — Email Alert Agent
Sends 24-hour change digest via Office365 SMTP (no-reply@thub.tech).

SMTP config (matches existing THub infrastructure):
  host: smtp.office365.com
  port: 587
  user: no-reply@thub.tech
  pass: NO_REPLY_MAIL_PASSWORD env var
  tls:  STARTTLS + SSLv3 ciphers
"""
import logging
import os
from datetime import datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from app.config import get_settings
from app.database import SessionLocal
from app.models import Company, ChangeLog, PageChange, DocumentRegistry, EmailSetting
from app.utils.email_template import build_email_html
from app.workflow.state import PipelineState

logger = logging.getLogger(__name__)
settings = get_settings()

# Office365 SMTP constants (matching THub nodemailer config)
_SMTP_HOST    = "smtp.office365.com"
_SMTP_PORT    = 587
_SMTP_USER    = "no-reply@thub.tech"
_SMTP_PASS    = os.getenv("NO_REPLY_MAIL_PASSWORD", settings.smtp_password)


def email_agent(state: PipelineState) -> dict:
    """LangGraph node — send email if changes exist."""
    if not state.get("has_changes"):
        logger.info("[M8-EMAIL] No changes detected — skipping email")
        return {"email_sent": False}

    db = SessionLocal()
    try:
        company = db.query(Company).get(state["company_id"])
        if not company:
            return {"email_sent": False}

        recipients = _get_recipients(db)
        if not recipients:
            logger.warning("[M8-EMAIL] No recipients configured — skipping email")
            return {"email_sent": False}

        # Collect 24h data
        doc_changes, page_changes = _collect_24h_data(db, state["company_id"])

        # Build HTML body
        html_body = build_email_html(
            company_names=[company.company_name],
            doc_changes=doc_changes,
            page_changes=page_changes,
            generated_at=datetime.utcnow(),
        )

        subject = (
            f"FinWatch Alert — {company.company_name} — "
            f"{len(doc_changes)} doc change(s), {len(page_changes)} page change(s) — "
            f"{datetime.utcnow().strftime('%Y-%m-%d')}"
        )

        excel_path = state.get("excel_path")
        success = _send_email(recipients, subject, html_body, excel_path)
        logger.info(f"[M8-EMAIL] Email {'sent' if success else 'FAILED'} to {recipients}")
        return {"email_sent": success}
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Gmail API via Google OAuth2
# ─────────────────────────────────────────────────────────────────────────────
def _send_email(recipients: List[str], subject: str, html_body: str, attachment_path: Optional[str] = None) -> bool:
    """Send via Office365 SMTP (no-reply@thub.tech)."""
    return _send_via_smtp(recipients, subject, html_body, attachment_path)


def _send_via_smtp(recipients: List[str], subject: str, html_body: str, attachment_path: Optional[str]) -> bool:
    """Office365 SMTP — mirrors THub nodemailer config exactly."""
    import smtplib
    import ssl
    try:
        msg = _build_mime(recipients, subject, html_body, attachment_path)
        # SSLv3 ciphers matching the THub nodemailer tls config
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT")
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.ehlo()
            smtp.login(_SMTP_USER, _SMTP_PASS)
            smtp.sendmail(_SMTP_USER, recipients, msg.as_string())
        logger.info(f"[M8-EMAIL] Sent via Office365 to {recipients}")
        return True
    except Exception as e:
        logger.error(f"[M8-EMAIL] Office365 SMTP failed: {e}")
        return False


def _build_mime(recipients: List[str], subject: str, html_body: str, attachment_path: Optional[str]) -> MIMEMultipart:
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["To"] = ", ".join(recipients)
    msg["From"] = _SMTP_USER  # always no-reply@thub.tech

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText("Please view this email in an HTML-capable client.", "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    if attachment_path and os.path.exists(attachment_path):
        filename = os.path.basename(attachment_path)
        with open(attachment_path, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(part)

    return msg


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _collect_24h_data(db, company_id: int):
    cutoff = datetime.utcnow() - timedelta(hours=24)
    docs = db.query(DocumentRegistry).filter(DocumentRegistry.company_id == company_id).all()
    doc_ids = [d.id for d in docs]
    doc_map = {d.id: d for d in docs}

    changes = db.query(ChangeLog).filter(
        ChangeLog.document_id.in_(doc_ids), ChangeLog.detected_at >= cutoff
    ).all()
    doc_changes = [
        {
            "company": doc_map.get(c.document_id, {}).company.company_name if c.document_id in doc_map else "",
            "change_type": c.change_type,
            "url": doc_map[c.document_id].document_url if c.document_id in doc_map else "",
            "doc_type": doc_map[c.document_id].doc_type if c.document_id in doc_map else "",
            "detected_at": str(c.detected_at)[:19],
        }
        for c in changes
    ]

    page_changes = db.query(PageChange).filter(
        PageChange.company_id == company_id, PageChange.detected_at >= cutoff
    ).all()
    pc_list = [
        {
            "company": "",
            "change_type": p.change_type,
            "page_url": p.page_url,
            "diff_summary": p.diff_summary,
            "detected_at": str(p.detected_at)[:19],
        }
        for p in page_changes
    ]

    return doc_changes, pc_list


def _get_recipients(db) -> List[str]:
    es: Optional[EmailSetting] = db.query(EmailSetting).first()
    if es and es.recipients:
        return es.recipients if isinstance(es.recipients, list) else [es.recipients]
    return settings.get_recipients()



