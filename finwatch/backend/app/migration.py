"""Database migration helpers."""
from __future__ import annotations

import logging
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


def _alembic_config():
    from alembic.config import Config

    settings = get_settings()
    backend_root = Path(__file__).resolve().parents[1]
    config_path = backend_root / "alembic.ini"
    cfg = Config(str(config_path))
    cfg.set_main_option("script_location", str(backend_root / "alembic_migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.effective_database_url)
    return cfg


def ensure_schema_at_head() -> str:
    """Upgrade DB schema to Alembic head revision."""
    from alembic import command

    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    logger.info("[MIGRATION] Database upgraded to head")
    return "upgraded"
