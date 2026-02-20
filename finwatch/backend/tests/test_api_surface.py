import unittest

from fastapi.testclient import TestClient

from app.main import app


class ApiSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    def test_health_and_ready(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        payload = health.json()
        self.assertEqual(payload.get("status"), "ok")
        self.assertIn("service", payload)
        self.assertIn("version", payload)

        ready = self.client.get("/ready")
        self.assertEqual(ready.status_code, 200)
        ready_payload = ready.json()
        self.assertEqual(ready_payload.get("status"), "ready")
        self.assertEqual(ready_payload.get("database"), "ok")

    def test_api_alias_endpoints_exist(self):
        api_health = self.client.get("/api/health")
        self.assertEqual(api_health.status_code, 200)

        api_ready = self.client.get("/api/ready")
        self.assertEqual(api_ready.status_code, 200)

        metadata_alias = self.client.get("/api/metadata", follow_redirects=False)
        self.assertIn(metadata_alias.status_code, (302, 307))
        self.assertIn("/api/documents/metadata/", metadata_alias.headers.get("location", ""))

        changes_alias = self.client.get("/api/changes/document", follow_redirects=False)
        self.assertIn(changes_alias.status_code, (302, 307))
        self.assertIn("/api/documents/changes/document", changes_alias.headers.get("location", ""))

    def test_core_list_and_summary_endpoints(self):
        endpoints = [
            "/api/companies/",
            "/api/documents/",
            "/api/documents/metadata/",
            "/api/documents/changes/",
            "/api/documents/sources/summary",
            "/api/documents/retries",
            "/api/webwatch/snapshots",
            "/api/webwatch/changes",
            "/api/crawl/diagnostics",
            "/api/crawl/diagnostics/summary",
            "/api/settings/",
        ]
        for path in endpoints:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, msg=f"{path} failed: {response.text}")

        analytics = self.client.get("/api/analytics/overview?hours=24")
        self.assertEqual(analytics.status_code, 200)
        payload = analytics.json()
        self.assertIsInstance(payload, dict)


if __name__ == "__main__":
    unittest.main()
