import os
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Company, DocumentRegistry
from app.utils.time import utc_now_naive


class CompanyIntakeAndDownloadsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.query(DocumentRegistry).filter(DocumentRegistry.document_url.like("https://intake-test.local/%")).delete()
        self.db.query(Company).filter(Company.company_slug.like("intake-test-%")).delete()
        self.db.commit()
        self.db.close()

    def test_intake_run_creates_or_reuses_company(self):
        payload = {
            "company_name": f"Intake Test {uuid.uuid4().hex[:6]}",
            "website_url": "https://intake-test.local/investors",
            "crawl_depth": 2,
            "reuse_existing": True,
        }

        with patch("app.api.companies.run_company_sync", return_value={"company": payload["company_name"], "docs_downloaded": 2}):
            response = self.client.post("/api/companies/intake-run", json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("company", body)
        self.assertIn("run_result", body)
        self.assertIn("overview", body)
        self.assertEqual(body["company"]["company_name"], payload["company_name"])

    def test_company_download_view_period_filter(self):
        slug = f"intake-test-{uuid.uuid4().hex[:8]}"
        company = Company(
            company_name=f"Intake Test {uuid.uuid4().hex[:6]}",
            company_slug=slug,
            website_url="https://intake-test.local",
            crawl_depth=2,
            active=True,
        )
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)

        now = utc_now_naive()
        self.db.add_all(
            [
                DocumentRegistry(
                    company_id=company.id,
                    document_url=f"https://intake-test.local/{uuid.uuid4().hex}-quarterly.pdf",
                    doc_type="FINANCIAL|QUARTERLY_RESULTS",
                    local_path=os.path.join("downloads", slug, "QuarterlyReports", "q1.pdf"),
                    status="NEW",
                    metadata_extracted=False,
                    last_checked=now,
                ),
                DocumentRegistry(
                    company_id=company.id,
                    document_url=f"https://intake-test.local/{uuid.uuid4().hex}-annual.pdf",
                    doc_type="FINANCIAL|ANNUAL_REPORT",
                    local_path=os.path.join("downloads", slug, "AnnualReports", "annual.pdf"),
                    status="NEW",
                    metadata_extracted=False,
                    last_checked=now,
                ),
            ]
        )
        self.db.commit()

        response = self.client.get(f"/api/documents/company/{company.id}/download-view?period=QUARTERLY")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["quarterly_documents"], 1)
        self.assertEqual(payload["summary"]["yearly_documents"], 0)
        self.assertTrue(all(row["period_bucket"] == "QUARTERLY" for row in payload["records"]))


if __name__ == "__main__":
    unittest.main()
