"""Runtime schema compatibility fixes for additive columns."""
from __future__ import annotations

from sqlalchemy import inspect, text

from app.database import engine
from app.models import Base


def ensure_runtime_schema_compatibility() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "job_runs" in tables:
        columns = {column["name"] for column in inspector.get_columns("job_runs")}
        statements = []
        if "duration_ms" not in columns:
            statements.append("ALTER TABLE job_runs ADD COLUMN duration_ms INTEGER")
        if "items_processed" not in columns:
            statements.append("ALTER TABLE job_runs ADD COLUMN items_processed INTEGER")
        if "error_count" not in columns:
            statements.append("ALTER TABLE job_runs ADD COLUMN error_count INTEGER")

        if statements:
            with engine.begin() as conn:
                for stmt in statements:
                    conn.execute(text(stmt))

    if "crawl_diagnostics" not in tables and "crawl_diagnostics" in Base.metadata.tables:
        Base.metadata.tables["crawl_diagnostics"].create(bind=engine, checkfirst=True)

    if "document_registry" in tables:
        columns = {column["name"] for column in inspector.get_columns("document_registry")}
        statements = []
        if "classifier_confidence" not in columns:
            statements.append("ALTER TABLE document_registry ADD COLUMN classifier_confidence FLOAT")
        if "classifier_version" not in columns:
            statements.append("ALTER TABLE document_registry ADD COLUMN classifier_version VARCHAR(50)")
        if "needs_review" not in columns:
            statements.append("ALTER TABLE document_registry ADD COLUMN needs_review BOOLEAN")
        if statements:
            with engine.begin() as conn:
                for stmt in statements:
                    conn.execute(text(stmt))
