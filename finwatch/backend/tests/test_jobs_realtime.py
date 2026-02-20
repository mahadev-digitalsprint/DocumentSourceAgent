import unittest

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import JobRun


class JobsRealtimeApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    def test_run_all_direct_returns_run_id(self):
        db = SessionLocal()
        try:
            db.query(JobRun).filter(
                JobRun.trigger_type.in_(["PIPELINE", "PIPELINE_ALL"]),
                JobRun.status.in_(["QUEUED", "RUNNING", "RETRY", "RETRYING", "PENDING", "STARTED", "PROGRESS"]),
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

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
