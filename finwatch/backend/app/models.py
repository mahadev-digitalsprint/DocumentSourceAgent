"""
All SQLAlchemy ORM models — 9 tables defining the complete data schema.
"""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, ForeignKey, BigInteger, JSON, Float,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


# ─────────────────────────────────────────────────────────────────────────────
# 1. Companies
# ─────────────────────────────────────────────────────────────────────────────
class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False)
    company_slug = Column(String(255), unique=True, nullable=False, index=True)
    website_url = Column(Text, nullable=False)
    crawl_depth = Column(Integer, default=3)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    documents = relationship("DocumentRegistry", back_populates="company", cascade="all, delete-orphan")
    page_snapshots = relationship("PageSnapshot", back_populates="company", cascade="all, delete-orphan")
    page_changes = relationship("PageChange", back_populates="company", cascade="all, delete-orphan")
    errors = relationship("ErrorLog", back_populates="company", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Document Registry
# ─────────────────────────────────────────────────────────────────────────────
class DocumentRegistry(Base):
    __tablename__ = "document_registry"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    document_url = Column(Text, unique=True, nullable=False)
    file_hash = Column(String(64))           # SHA-256 of binary content
    etag = Column(String(255))
    last_modified_header = Column(String(255))
    local_path = Column(Text)
    doc_type = Column(String(100), default="Unknown")
    file_size_bytes = Column(BigInteger)
    page_count = Column(Integer)
    is_scanned = Column(Boolean, default=False)
    language = Column(String(50))
    status = Column(String(50), default="NEW")  # NEW|UNCHANGED|UPDATED|FAILED
    metadata_extracted = Column(Boolean, default=False)
    first_page_text = Column(Text)               # cached for classify/display
    classifier_confidence = Column(Float, nullable=True)
    classifier_version = Column(String(50), nullable=True)
    needs_review = Column(Boolean, default=False)
    last_checked = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    company = relationship("Company", back_populates="documents")
    meta_record = relationship("MetadataRecord", back_populates="document", uselist=False, cascade="all, delete-orphan")
    change_logs = relationship("ChangeLog", back_populates="document", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Metadata Records (10 canonical LLM-extracted fields)
# ─────────────────────────────────────────────────────────────────────────────
class MetadataRecord(Base):
    __tablename__ = "metadata_records"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("document_registry.id", ondelete="CASCADE"), unique=True, nullable=False)

    headline = Column(Text)
    filing_date = Column(String(20))
    filing_data_source = Column(Text)
    language = Column(String(100))
    period_end_date = Column(String(20))
    document_type = Column(String(100))
    income_statement = Column(Boolean)
    preliminary_document = Column(Boolean)
    note_flag = Column(Boolean)
    audit_flag = Column(Boolean)

    raw_llm_response = Column(JSON)            # store full LLM JSON for audit

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    document = relationship("DocumentRegistry", back_populates="meta_record")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Document Change Log
# ─────────────────────────────────────────────────────────────────────────────
class ChangeLog(Base):
    __tablename__ = "change_logs"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("document_registry.id", ondelete="CASCADE"), nullable=False)
    change_type = Column(String(50))     # NEW | UPDATED | REMOVED
    old_hash = Column(String(64))
    new_hash = Column(String(64))
    detected_at = Column(DateTime, server_default=func.now())

    document = relationship("DocumentRegistry", back_populates="change_logs")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Page Snapshots (WebWatch)
# ─────────────────────────────────────────────────────────────────────────────
class PageSnapshot(Base):
    __tablename__ = "page_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    page_url = Column(Text, nullable=False)
    content_hash = Column(String(64))           # SHA-256 of page text
    content_text = Column(Text)                 # full page text (truncated 50k)
    pdf_urls_found = Column(JSON)               # list of PDF URLs on this page
    status_code = Column(Integer)               # HTTP status
    is_active = Column(Boolean, default=True)   # False = page was deleted
    last_seen = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    company = relationship("Company", back_populates="page_snapshots")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Page Changes (WebWatch diffs)
# ─────────────────────────────────────────────────────────────────────────────
class PageChange(Base):
    __tablename__ = "page_changes"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    page_url = Column(Text, nullable=False)
    change_type = Column(String(50))           # PAGE_ADDED|PAGE_DELETED|CONTENT_CHANGED|NEW_DOC_LINKED
    old_text = Column(Text)
    new_text = Column(Text)
    diff_summary = Column(Text)                # human-readable summary of what changed
    new_pdf_urls = Column(JSON)                # new PDF links discovered on page
    old_hash = Column(String(64))
    new_hash = Column(String(64))
    detected_at = Column(DateTime, server_default=func.now())

    company = relationship("Company", back_populates="page_changes")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Error Logs
# ─────────────────────────────────────────────────────────────────────────────
class ErrorLog(Base):
    __tablename__ = "error_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    document_url = Column(Text)
    step = Column(String(100))                 # crawl|webwatch|download|classify|parse|extract|excel|email
    error_type = Column(String(100))           # CRAWL_BLOCKED|OCR_FAILURE|LLM_TIMEOUT|DOWNLOAD_FAILED…
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    company = relationship("Company", back_populates="errors")


# ─────────────────────────────────────────────────────────────────────────────
# 8. Email Settings
# ─────────────────────────────────────────────────────────────────────────────
class EmailSetting(Base):
    __tablename__ = "email_settings"

    id = Column(Integer, primary_key=True, index=True)
    smtp_host = Column(String(255), default="smtp.gmail.com")
    smtp_port = Column(Integer, default=587)
    smtp_user = Column(String(255))
    smtp_password = Column(String(255))        # stored encrypted in prod
    email_from = Column(String(255))
    recipients = Column(JSON)                  # list of email strings
    send_on_change = Column(Boolean, default=True)
    daily_digest_hour = Column(Integer, default=6)  # 6 AM local
    updated_at = Column(DateTime, onupdate=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# 9. System Settings
# ─────────────────────────────────────────────────────────────────────────────
class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, onupdate=func.now())


# -----------------------------------------------------------------------------
# 10. Job Runs (operational history for queued/direct executions)
# -----------------------------------------------------------------------------
class JobRun(Base):
    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), unique=True, nullable=False, index=True)
    trigger_type = Column(String(50), nullable=False)   # PIPELINE|WEBWATCH|DIGEST|EXCEL
    mode = Column(String(20), nullable=False)           # QUEUED|DIRECT
    status = Column(String(30), nullable=False, default="QUEUED")  # QUEUED|RUNNING|DONE|FAILED|...
    celery_job_id = Column(String(64), index=True)

    company_id = Column(Integer, nullable=True)
    company_name = Column(String(255), nullable=True)

    result_payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    items_processed = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, onupdate=func.now())
