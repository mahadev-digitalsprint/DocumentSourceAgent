import os
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.config import get_settings
from app.migration import ensure_schema_at_head

ALEMBIC_AVAILABLE = True
try:
    import alembic  # noqa: F401
except Exception:
    ALEMBIC_AVAILABLE = False


@unittest.skipUnless(ALEMBIC_AVAILABLE, "alembic package is not installed in this environment")
class MigrationSafetyTests(unittest.TestCase):
    def test_upgrade_creates_schema_and_version_table(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_migrate.db"
            db_url = f"sqlite:///{db_path.as_posix()}"

            original_database_url = os.environ.get("DATABASE_URL")
            original_postgres_url = os.environ.get("POSTGRES_URL")
            try:
                os.environ["DATABASE_URL"] = db_url
                os.environ.pop("POSTGRES_URL", None)
                get_settings.cache_clear()

                result = ensure_schema_at_head()
                self.assertEqual(result, "upgraded")

                engine = create_engine(db_url)
                inspector = inspect(engine)
                tables = set(inspector.get_table_names())
                self.assertIn("alembic_version", tables)
                self.assertIn("job_runs", tables)
                columns = {column["name"] for column in inspector.get_columns("job_runs")}
                self.assertIn("duration_ms", columns)
                self.assertIn("items_processed", columns)
                self.assertIn("error_count", columns)
                doc_columns = {column["name"] for column in inspector.get_columns("document_registry")}
                self.assertIn("classifier_confidence", doc_columns)
                self.assertIn("classifier_version", doc_columns)
                self.assertIn("needs_review", doc_columns)
                engine.dispose()
            finally:
                if original_database_url is None:
                    os.environ.pop("DATABASE_URL", None)
                else:
                    os.environ["DATABASE_URL"] = original_database_url
                if original_postgres_url is None:
                    os.environ.pop("POSTGRES_URL", None)
                else:
                    os.environ["POSTGRES_URL"] = original_postgres_url
                get_settings.cache_clear()


if __name__ == "__main__":
    unittest.main()
