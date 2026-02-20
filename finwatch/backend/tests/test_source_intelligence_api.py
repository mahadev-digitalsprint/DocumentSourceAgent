import unittest
import uuid

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Company, DocumentRegistry, IngestionRetry
from app.utils.time import utc_now_naive


class SourceIntelligenceApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    def setUp(self):
        self.db = SessionLocal()
        self.company = Company(
            company_name=f"Source Test {uuid.uuid4().hex[:8]}",
            company_slug=f"source-test-{uuid.uuid4().hex[:10]}",
            website_url="https://example.com",
            crawl_depth=2,
            active=True,
        )
        self.db.add(self.company)
        self.db.commit()
        self.db.refresh(self.company)

        now = utc_now_naive()
        self.doc = DocumentRegistry(
            company_id=self.company.id,
            document_url=f"https://example.com/docs/{uuid.uuid4().hex}.pdf",
            file_hash="hash-a",
            doc_type="FINANCIAL|ANNUAL_REPORT",
            status="NEW",
            metadata_extracted=False,
            source_type="WEBSITE",
            source_domain="example.com",
            discovery_strategy="Sitemap",
            first_seen_at=now,
            last_seen_at=now,
            last_checked=now,
        )
        self.retry = IngestionRetry(
            company_id=self.company.id,
            document_url=f"https://example.com/dead/{uuid.uuid4().hex}.pdf",
            source_domain="example.com",
            reason_code="INVALID_PDF_SIGNATURE",
            failure_count=3,
            status="DEAD",
            last_error="bad signature",
            last_attempt_at=now,
        )
        self.db.add(self.doc)
        self.db.add(self.retry)
        self.db.commit()
        self.db.refresh(self.retry)

    def tearDown(self):
        self.db.query(IngestionRetry).filter(IngestionRetry.company_id == self.company.id).delete()
        self.db.query(DocumentRegistry).filter(DocumentRegistry.company_id == self.company.id).delete()
        self.db.query(Company).filter(Company.id == self.company.id).delete()
        self.db.commit()
        self.db.close()

    def test_source_summary_returns_domain_rows(self):
        response = self.client.get(f"/api/documents/sources/summary?company_id={self.company.id}&hours=168")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(row["source_domain"] == "example.com" for row in payload))

    def test_retries_list_and_update(self):
        list_response = self.client.get(f"/api/documents/retries?company_id={self.company.id}&status=DEAD")
        self.assertEqual(list_response.status_code, 200)
        items = list_response.json()
        self.assertTrue(any(item["id"] == self.retry.id for item in items))

        invalid_update = self.client.patch(f"/api/documents/retries/{self.retry.id}", json={"status": "INVALID"})
        self.assertEqual(invalid_update.status_code, 400)
        self.assertEqual(invalid_update.json()["detail"]["code"], "INVALID_RETRY_STATUS")

        resolve_update = self.client.patch(f"/api/documents/retries/{self.retry.id}", json={"status": "RESOLVED"})
        self.assertEqual(resolve_update.status_code, 200)
        self.assertEqual(resolve_update.json()["status"], "RESOLVED")


if __name__ == "__main__":
    unittest.main()
