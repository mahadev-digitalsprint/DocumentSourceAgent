import uuid
import unittest

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Company, CrawlDiagnostic
from app.utils.crawl_control import domain_control


class CrawlApiTests(unittest.TestCase):
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
            company_name=f"Crawl Test {uuid.uuid4().hex[:8]}",
            company_slug=f"crawl-test-{uuid.uuid4().hex[:10]}",
            website_url="https://example.com",
            crawl_depth=2,
            active=True,
        )
        self.db.add(self.company)
        self.db.commit()
        self.db.refresh(self.company)
        domain_control.clear()

    def tearDown(self):
        self.db.query(CrawlDiagnostic).filter(CrawlDiagnostic.company_id == self.company.id).delete()
        self.db.query(Company).filter(Company.id == self.company.id).delete()
        self.db.commit()
        self.db.close()
        domain_control.clear()

    def test_diagnostics_list_filters(self):
        self.db.add_all(
            [
                CrawlDiagnostic(
                    company_id=self.company.id,
                    domain="example.com",
                    strategy="BS4",
                    page_url="https://example.com/investor",
                    status_code=200,
                    blocked=False,
                    error_message=None,
                    retry_count=0,
                    duration_ms=21,
                ),
                CrawlDiagnostic(
                    company_id=self.company.id,
                    domain="example.com",
                    strategy="Regex",
                    page_url="https://example.com/results",
                    status_code=403,
                    blocked=True,
                    error_message="blocked by waf",
                    retry_count=0,
                    duration_ms=38,
                ),
            ]
        )
        self.db.commit()

        response = self.client.get(f"/api/crawl/diagnostics?hours=24&company_id={self.company.id}&strategy=BS4")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["strategy"], "BS4")
        self.assertEqual(payload[0]["company_id"], self.company.id)

        blocked_resp = self.client.get(f"/api/crawl/diagnostics?hours=24&company_id={self.company.id}&blocked=true")
        self.assertEqual(blocked_resp.status_code, 200)
        blocked_payload = blocked_resp.json()
        self.assertTrue(all(row["blocked"] is True for row in blocked_payload))

    def test_diagnostics_summary_and_cooldowns(self):
        self.db.add_all(
            [
                CrawlDiagnostic(
                    company_id=self.company.id,
                    domain="example.com",
                    strategy="BS4",
                    page_url="https://example.com/a",
                    status_code=200,
                    blocked=False,
                    duration_ms=10,
                ),
                CrawlDiagnostic(
                    company_id=self.company.id,
                    domain="example.com",
                    strategy="BS4",
                    page_url="https://example.com/b",
                    status_code=503,
                    blocked=True,
                    duration_ms=30,
                ),
                CrawlDiagnostic(
                    company_id=self.company.id,
                    domain="cdn.example.com",
                    strategy="Regex",
                    page_url="https://example.com/c",
                    status_code=200,
                    blocked=False,
                    error_message="parse error",
                    duration_ms=40,
                ),
            ]
        )
        self.db.commit()
        domain_control.mark_blocked("example.com", 120)

        summary_resp = self.client.get(f"/api/crawl/diagnostics/summary?hours=24&company_id={self.company.id}")
        self.assertEqual(summary_resp.status_code, 200)
        summary = summary_resp.json()
        self.assertGreaterEqual(summary["total_requests"], 3)
        self.assertGreaterEqual(summary["blocked_requests"], 1)
        self.assertGreaterEqual(summary["error_requests"], 1)
        self.assertGreaterEqual(summary["p95_duration_ms"], 30)
        self.assertGreaterEqual(summary["active_domain_cooldowns"], 1)
        self.assertIsInstance(summary["strategy_breakdown"], list)

        cooldown_resp = self.client.get("/api/crawl/cooldowns")
        self.assertEqual(cooldown_resp.status_code, 200)
        blocked_domains = cooldown_resp.json()["blocked_domains"]
        self.assertTrue(any(row["domain"] == "example.com" for row in blocked_domains))

        clear_resp = self.client.delete("/api/crawl/cooldowns/example.com")
        self.assertEqual(clear_resp.status_code, 200)
        self.assertEqual(clear_resp.json()["domain"], "example.com")


if __name__ == "__main__":
    unittest.main()
