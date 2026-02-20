"""API router — Company CRUD."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import re

from app.database import get_db
from app.models import Company

router = APIRouter()


class CompanyCreate(BaseModel):
    company_name: str
    website_url: str
    crawl_depth: int = 3


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


@router.get("/", response_model=List[CompanyOut])
def list_companies(db: Session = Depends(get_db)):
    return db.query(Company).order_by(Company.company_name).all()


@router.post("/", response_model=CompanyOut, status_code=201)
def create_company(body: CompanyCreate, db: Session = Depends(get_db)):
    slug = _slugify(body.company_name)
    if db.query(Company).filter(Company.company_slug == slug).first():
        raise HTTPException(400, "Company already exists")
    c = Company(company_name=body.company_name, company_slug=slug,
                website_url=body.website_url, crawl_depth=body.crawl_depth)
    db.add(c); db.commit(); db.refresh(c)
    return c


@router.post("/bulk", response_model=List[CompanyOut], status_code=201)
def bulk_create(companies: List[CompanyCreate], db: Session = Depends(get_db)):
    created = []
    for body in companies:
        slug = _slugify(body.company_name)
        if not db.query(Company).filter(Company.company_slug == slug).first():
            c = Company(company_name=body.company_name, company_slug=slug,
                        website_url=body.website_url, crawl_depth=body.crawl_depth)
            db.add(c); db.flush(); created.append(c)
    db.commit()
    return created


@router.delete("/{company_id}", status_code=204)
def delete_company(company_id: int, db: Session = Depends(get_db)):
    c = db.query(Company).get(company_id)
    if not c:
        raise HTTPException(404, "Not found")
    db.delete(c); db.commit()


@router.patch("/{company_id}/toggle")
def toggle_active(company_id: int, db: Session = Depends(get_db)):
    c = db.query(Company).get(company_id)
    if not c:
        raise HTTPException(404, "Not found")
    c.active = not c.active
    db.commit()
    return {"active": c.active}
