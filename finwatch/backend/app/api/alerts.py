"""API router — Email alert configuration."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.models import EmailSetting

router = APIRouter()


class EmailSettingIn(BaseModel):
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    recipients: List[str] = []
    send_on_change: bool = True
    daily_digest_hour: int = 6


@router.get("/")
def get_alert_config(db: Session = Depends(get_db)):
    es = db.query(EmailSetting).first()
    if not es:
        return {"configured": False}
    return {
        "configured": True,
        "smtp_host": es.smtp_host, "smtp_port": es.smtp_port,
        "smtp_user": es.smtp_user, "email_from": es.email_from,
        "recipients": es.recipients or [],
        "send_on_change": es.send_on_change,
        "daily_digest_hour": es.daily_digest_hour,
    }


@router.post("/")
def save_alert_config(body: EmailSettingIn, db: Session = Depends(get_db)):
    es = db.query(EmailSetting).first()
    if es:
        es.smtp_host = body.smtp_host; es.smtp_port = body.smtp_port
        es.smtp_user = body.smtp_user; es.smtp_password = body.smtp_password
        es.email_from = body.email_from; es.recipients = body.recipients
        es.send_on_change = body.send_on_change; es.daily_digest_hour = body.daily_digest_hour
    else:
        es = EmailSetting(**body.dict())
        db.add(es)
    db.commit()
    return {"saved": True}


@router.post("/test")
def test_email(db: Session = Depends(get_db)):
    from app.agents.email_agent import _send_email, _get_recipients
    from datetime import datetime
    recipients = _get_recipients(db)
    if not recipients:
        return {"sent": False, "error": "No recipients configured"}
    ok = _send_email(recipients, "FinWatch — Test Email", "<h2>FinWatch test email works ✅</h2>", None)
    return {"sent": ok}
