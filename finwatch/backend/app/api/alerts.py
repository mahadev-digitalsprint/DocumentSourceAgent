"""API router - Email alert configuration."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EmailSetting

router = APIRouter()

DEFAULT_SMTP_HOST = "smtp.office365.com"
DEFAULT_SMTP_PORT = 587
DEFAULT_SMTP_USER = "no-reply@thub.tech"
DEFAULT_EMAIL_FROM = "no-reply@thub.tech"


class EmailSettingIn(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    email_from: Optional[str] = None
    recipients: Optional[List[str]] = None
    receiver_email: Optional[str] = None
    send_on_change: bool = True
    daily_digest_hour: int = Field(default=6, ge=0, le=23)


class ReceiverOnlyIn(BaseModel):
    receiver_email: str
    send_on_change: bool = True
    daily_digest_hour: int = Field(default=6, ge=0, le=23)


class TestEmailIn(BaseModel):
    receiver_email: Optional[str] = None


def _is_valid_email(value: str) -> bool:
    email = (value or "").strip()
    if "@" not in email:
        return False
    local, _, domain = email.partition("@")
    if not local or not domain:
        return False
    if "." not in domain:
        return False
    return True


def _normalize_recipients(value: Optional[List[str]], receiver_email: Optional[str]) -> List[str]:
    emails: List[str] = []
    if value:
        emails.extend(value)
    if receiver_email:
        emails.append(receiver_email)
    normalized: List[str] = []
    seen = set()
    for raw in emails:
        candidate = (raw or "").strip().lower()
        if not candidate:
            continue
        if not _is_valid_email(candidate):
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_EMAIL", "message": "Invalid receiver email format", "details": {"email": raw}},
            )
        if candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


def _upsert_email_setting(
    db: Session,
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    email_from: str,
    recipients: List[str],
    send_on_change: bool,
    daily_digest_hour: int,
):
    es = db.query(EmailSetting).first()
    if es:
        es.smtp_host = smtp_host
        es.smtp_port = smtp_port
        es.smtp_user = smtp_user
        es.smtp_password = smtp_password
        es.email_from = email_from
        es.recipients = recipients
        es.send_on_change = send_on_change
        es.daily_digest_hour = daily_digest_hour
    else:
        es = EmailSetting(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            email_from=email_from,
            recipients=recipients,
            send_on_change=send_on_change,
            daily_digest_hour=daily_digest_hour,
        )
        db.add(es)
    db.commit()
    db.refresh(es)
    return es


@router.get("/")
def get_alert_config(db: Session = Depends(get_db)):
    es = db.query(EmailSetting).first()
    if not es:
        return {"configured": False}
    return {
        "configured": True,
        "smtp_host": es.smtp_host,
        "smtp_port": es.smtp_port,
        "smtp_user": es.smtp_user,
        "email_from": es.email_from,
        "recipients": es.recipients or [],
        "send_on_change": es.send_on_change,
        "daily_digest_hour": es.daily_digest_hour,
    }


@router.get("/simple")
def get_simple_alert_config(db: Session = Depends(get_db)):
    es = db.query(EmailSetting).first()
    recipients = (es.recipients or []) if es else []
    return {
        "configured": bool(es and recipients),
        "receiver_email": recipients[0] if recipients else "",
        "send_on_change": es.send_on_change if es else True,
        "daily_digest_hour": es.daily_digest_hour if es else 6,
        "sender_email": (es.email_from if es and es.email_from else DEFAULT_EMAIL_FROM),
    }


@router.post("/")
def save_alert_config(body: EmailSettingIn, db: Session = Depends(get_db)):
    recipients = _normalize_recipients(body.recipients, body.receiver_email)
    if not recipients:
        raise HTTPException(
            status_code=400,
            detail={"code": "NO_RECIPIENTS", "message": "At least one receiver email is required", "details": {}},
        )

    existing = db.query(EmailSetting).first()
    smtp_password = body.smtp_password or (existing.smtp_password if existing else "")
    es = _upsert_email_setting(
        db,
        smtp_host=(body.smtp_host or (existing.smtp_host if existing else DEFAULT_SMTP_HOST)),
        smtp_port=int(body.smtp_port or (existing.smtp_port if existing else DEFAULT_SMTP_PORT)),
        smtp_user=(body.smtp_user or (existing.smtp_user if existing else DEFAULT_SMTP_USER)),
        smtp_password=smtp_password,
        email_from=(body.email_from or (existing.email_from if existing else DEFAULT_EMAIL_FROM)),
        recipients=recipients,
        send_on_change=bool(body.send_on_change),
        daily_digest_hour=int(body.daily_digest_hour),
    )
    return {"saved": True, "configured": True, "receiver_email": (es.recipients or [""])[0]}


@router.post("/simple")
def save_simple_alert_config(body: ReceiverOnlyIn, db: Session = Depends(get_db)):
    recipients = _normalize_recipients(None, body.receiver_email)
    existing = db.query(EmailSetting).first()
    smtp_password = existing.smtp_password if existing else ""
    es = _upsert_email_setting(
        db,
        smtp_host=(existing.smtp_host if existing and existing.smtp_host else DEFAULT_SMTP_HOST),
        smtp_port=int(existing.smtp_port if existing and existing.smtp_port else DEFAULT_SMTP_PORT),
        smtp_user=(existing.smtp_user if existing and existing.smtp_user else DEFAULT_SMTP_USER),
        smtp_password=smtp_password,
        email_from=(existing.email_from if existing and existing.email_from else DEFAULT_EMAIL_FROM),
        recipients=recipients,
        send_on_change=bool(body.send_on_change),
        daily_digest_hour=int(body.daily_digest_hour),
    )
    return {"saved": True, "configured": True, "receiver_email": (es.recipients or [""])[0]}


@router.post("/test")
def test_email(body: Optional[TestEmailIn] = None, db: Session = Depends(get_db)):
    from app.agents.email_agent import _get_recipients, _send_email

    recipients = _get_recipients(db)
    if body and body.receiver_email:
        recipients = _normalize_recipients(None, body.receiver_email)
    if not recipients:
        return {"sent": False, "error": "No recipients configured"}
    ok = _send_email(recipients, "FinWatch - Test Email", "<h2>FinWatch test email works</h2>", None)
    return {"sent": ok}
