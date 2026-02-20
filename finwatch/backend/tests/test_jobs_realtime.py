import unittest

from fastapi.testclient import TestClient

from app.main import app


class JobsRealtimeApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_run_all_direct_returns_run_id(self):
        response = self.client.post("/api/jobs/run-all-direct")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("run_id", payload)
        self.assertTrue(payload.get("run_id"))
        self.assertEqual(payload.get("status"), "DONE")

    def test_history_returns_list(self):
        response = self.client.get("/api/jobs/history?limit=5")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsInstance(payload, list)

    def test_events_endpoint_streams(self):
        response = self.client.get("/api/jobs/events?poll_seconds=0.5&limit=5&once=true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("content-type"), "text/event-stream; charset=utf-8")
        self.assertIn(": ping", response.text)


if __name__ == "__main__":
    unittest.main()
