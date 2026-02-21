import tempfile
import unittest
import uuid
from pathlib import Path

from app.agents.classify_agent import classify_agent
from app.database import SessionLocal
from app.models import Company, DocumentRegistry
from app.utils.time import utc_now_naive


class ClassifyRehomeTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.company = Company(
            company_name=f"Rehome Test {uuid.uuid4().hex[:8]}",
            company_slug=f"rehome-test-{uuid.uuid4().hex[:10]}",
            website_url="https://example.com",
            crawl_depth=2,
            active=True,
        )
        self.db.add(self.company)
        self.db.commit()
        self.db.refresh(self.company)

    def tearDown(self):
        self.db.query(DocumentRegistry).filter(DocumentRegistry.company_id == self.company.id).delete()
        self.db.query(Company).filter(Company.id == self.company.id).delete()
        self.db.commit()
        self.db.close()

    def test_classify_moves_document_into_annual_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / self.company.company_slug / "Other"
            source_dir.mkdir(parents=True, exist_ok=True)
            source_file = source_dir / "annual-report-2025.pdf"
            source_file.write_bytes(b"%PDF-1.7\n")

            now = utc_now_naive()
            doc = DocumentRegistry(
                company_id=self.company.id,
                document_url=f"https://example.com/{source_file.name}",
                file_hash="x",
                local_path=str(source_file),
                doc_type="Unknown",
                status="NEW",
                metadata_extracted=False,
                last_checked=now,
            )
            self.db.add(doc)
            self.db.commit()
            self.db.refresh(doc)

            classify_agent({"downloaded_docs": [{"doc_id": doc.id, "status": "NEW", "local_path": str(source_file)}]})

            self.db.refresh(doc)
            self.assertIn("AnnualReports", doc.local_path or "")
            self.assertTrue(Path(doc.local_path).exists())
            self.assertFalse(source_file.exists())


if __name__ == "__main__":
    unittest.main()
