"""Company APIs: CRUD, quick intake-run, and download overview."""
from __future__ import annotations

import os
import re
from typing import List
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company, DocumentRegistry, SystemSetting
from app.services.pipeline_service import run_company_sync

router = APIRouter()


class CompanyCreate(BaseModel):
    company_name: str
    website_url: str
    crawl_depth: int = 3


class CompanyIntakeRunIn(BaseModel):
    company_name: str = Field(min_length=2, max_length=255)
    website_url: str = Field(min_length=8, max_length=2000)
    crawl_depth: int = Field(default=3, ge=1, le=8)
    reuse_existing: bool = True


class CompanyOut(BaseModel):
    id: int
    company_name: str
    company_slug: str
    website_url: str
    crawl_depth: int
    active: bool

    class Config:
        from_attributes = True


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _validate_url(url: str) -> str:
    clean = (url or "").strip()
    parsed = urlparse(clean)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(400, "website_url must be a valid http/https URL")
    return clean


def _base_folder(db: Session) -> str:
    setting = db.query(SystemSetting).filter(SystemSetting.key == "base_path").first()
    from app.config import get_settings

    return setting.value if setting else get_settings().base_download_path


def _period_from_doc_type(doc_type: str, url: str) -> str:
    text = f"{doc_type or ''} {url or ''}".lower()
    if any(token in text for token in ["quarter", "q1", "q2", "q3", "q4", "half-year", "half year", "interim"]):
        return "QUARTERLY"
    if any(token in text for token in ["annual", "yearly", "10-k", "20-f", "full year", "fy"]):
        return "YEARLY"
    return "OTHER"


def _company_overview(db: Session, company_id: int) -> dict:
    docs = db.query(DocumentRegistry).filter(DocumentRegistry.company_id == company_id).all()
    total = len(docs)
    quarterly = 0
    yearly = 0
    financial = 0
    non_financial = 0
    folders = set()

    for doc in docs:
        period = _period_from_doc_type(doc.doc_type or "", doc.document_url or "")
        if period == "QUARTERLY":
            quarterly += 1
        elif period == "YEARLY":
            yearly += 1

        if (doc.doc_type or "").startswith("FINANCIAL"):
            financial += 1
        elif (doc.doc_type or "").startswith("NON_FINANCIAL"):
            non_financial += 1

        if doc.local_path:
            folders.add(os.path.dirname(doc.local_path))

    return {
        "documents_total": total,
        "quarterly_documents": quarterly,
        "yearly_documents": yearly,
        "other_documents": max(0, total - quarterly - yearly),
        "financial_documents": financial,
        "non_financial_documents": non_financial,
        "download_folders": sorted(path for path in folders if path),
    }


@router.get("/", response_model=List[CompanyOut])
def list_companies(db: Session = Depends(get_db)):
    return db.query(Company).order_by(Company.company_name).all()


@router.post("/", response_model=CompanyOut, status_code=201)
def create_company(body: CompanyCreate, db: Session = Depends(get_db)):
    website_url = _validate_url(body.website_url)
    slug = _slugify(body.company_name)
    if db.query(Company).filter(Company.company_slug == slug).first():
        raise HTTPException(400, "Company already exists")
    company = Company(
        company_name=body.company_name,
        company_slug=slug,
        website_url=website_url,
        crawl_depth=body.crawl_depth,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.post("/bulk", response_model=List[CompanyOut], status_code=201)
def bulk_create(companies: List[CompanyCreate], db: Session = Depends(get_db)):
    created = []
    for body in companies:
        website_url = _validate_url(body.website_url)
        slug = _slugify(body.company_name)
        if not db.query(Company).filter(Company.company_slug == slug).first():
            company = Company(
                company_name=body.company_name,
                company_slug=slug,
                website_url=website_url,
                crawl_depth=body.crawl_depth,
            )
            db.add(company)
            db.flush()
            created.append(company)
    db.commit()
    return created


@router.delete("/{company_id}", status_code=204)
def delete_company(company_id: int, db: Session = Depends(get_db)):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Not found")
    db.delete(company)
    db.commit()


@router.patch("/{company_id}/toggle")
def toggle_active(company_id: int, db: Session = Depends(get_db)):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Not found")
    company.active = not company.active
    db.commit()
    return {"active": company.active}


@router.get("/{company_id}/overview")
def company_overview(company_id: int, db: Session = Depends(get_db)):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Not found")
    return {
        "company": CompanyOut.model_validate(company).model_dump(),
        "overview": _company_overview(db, company_id),
    }


@router.post("/intake-run")
def intake_and_run(body: CompanyIntakeRunIn, db: Session = Depends(get_db)):
    company_name = body.company_name.strip()
    website_url = _validate_url(body.website_url)
    slug = _slugify(company_name)

    company = db.query(Company).filter(Company.company_slug == slug).first()
    if company and not body.reuse_existing:
        raise HTTPException(400, "Company already exists")

    if company:
        company.company_name = company_name
        company.website_url = website_url
        company.crawl_depth = body.crawl_depth
        company.active = True
    else:
        company = Company(
            company_name=company_name,
            company_slug=slug,
            website_url=website_url,
            crawl_depth=body.crawl_depth,
            active=True,
        )
        db.add(company)
    db.commit()
    db.refresh(company)

    run_result = run_company_sync(company, _base_folder(db))
    return {
        "company": CompanyOut.model_validate(company).model_dump(),
        "run_result": run_result,
        "overview": _company_overview(db, company.id),
    }
