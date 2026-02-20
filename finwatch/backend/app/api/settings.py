"""API router — System settings (key-value store)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import SystemSetting

router = APIRouter()


class SettingIn(BaseModel):
    key: str
    value: str


@router.get("/")
def list_settings(db: Session = Depends(get_db)):
    return {s.key: s.value for s in db.query(SystemSetting).all()}


@router.post("/")
def upsert_setting(body: SettingIn, db: Session = Depends(get_db)):
    s = db.query(SystemSetting).filter(SystemSetting.key == body.key).first()
    if s:
        s.value = body.value
    else:
        db.add(SystemSetting(key=body.key, value=body.value))
    db.commit()
    return {"key": body.key, "value": body.value}


@router.get("/{key}")
def get_setting(key: str, db: Session = Depends(get_db)):
    s = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    return {"key": key, "value": s.value if s else None}
