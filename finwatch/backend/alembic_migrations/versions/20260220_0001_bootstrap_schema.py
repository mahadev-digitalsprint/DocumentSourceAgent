"""bootstrap schema and add job run analytics fields

Revision ID: 20260220_0001
Revises:
Create Date: 2026-02-20 23:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.models import Base

# revision identifiers, used by Alembic.
revision = "20260220_0001"
down_revision = None
branch_labels = None
depends_on = None


def _table_names(bind) -> set[str]:
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


def _column_names(bind, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table)}


def _ensure_tables(bind):
    existing_tables = _table_names(bind)
    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            table.create(bind=bind, checkfirst=True)


def _ensure_job_run_columns(bind):
    existing_tables = _table_names(bind)
    if "job_runs" not in existing_tables:
        return

    columns = _column_names(bind, "job_runs")
    if "duration_ms" not in columns:
        op.add_column("job_runs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    if "items_processed" not in columns:
        op.add_column("job_runs", sa.Column("items_processed", sa.Integer(), nullable=True))
    if "error_count" not in columns:
        op.add_column("job_runs", sa.Column("error_count", sa.Integer(), nullable=True))


def _ensure_document_registry_columns(bind):
    existing_tables = _table_names(bind)
    if "document_registry" not in existing_tables:
        return

    columns = _column_names(bind, "document_registry")
    if "classifier_confidence" not in columns:
        op.add_column("document_registry", sa.Column("classifier_confidence", sa.Float(), nullable=True))
    if "classifier_version" not in columns:
        op.add_column("document_registry", sa.Column("classifier_version", sa.String(length=50), nullable=True))
    if "needs_review" not in columns:
        op.add_column("document_registry", sa.Column("needs_review", sa.Boolean(), nullable=True))


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_tables(bind)
    _ensure_job_run_columns(bind)
    _ensure_document_registry_columns(bind)


def downgrade() -> None:
    bind = op.get_bind()
    existing_tables = _table_names(bind)
    if "document_registry" in existing_tables:
        columns = _column_names(bind, "document_registry")
        if "needs_review" in columns:
            op.drop_column("document_registry", "needs_review")
        if "classifier_version" in columns:
            op.drop_column("document_registry", "classifier_version")
        if "classifier_confidence" in columns:
            op.drop_column("document_registry", "classifier_confidence")
    if "job_runs" in existing_tables:
        columns = _column_names(bind, "job_runs")
        if "error_count" in columns:
            op.drop_column("job_runs", "error_count")
        if "items_processed" in columns:
            op.drop_column("job_runs", "items_processed")
        if "duration_ms" in columns:
            op.drop_column("job_runs", "duration_ms")
