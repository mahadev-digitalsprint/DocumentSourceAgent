"""SQLAlchemy engine/session setup."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

settings = get_settings()
db_url = settings.effective_database_url
is_postgres = db_url.startswith("postgresql")
is_sqlite = db_url.startswith("sqlite")

engine_kwargs = {"pool_pre_ping": True}
if is_postgres:
    engine_kwargs.update({"pool_size": 5, "max_overflow": 10})
elif is_sqlite:
    engine_kwargs.update({"connect_args": {"check_same_thread": False}})

engine = create_engine(db_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
