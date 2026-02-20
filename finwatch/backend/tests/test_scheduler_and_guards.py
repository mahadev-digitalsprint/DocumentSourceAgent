import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import JobRun


class SchedulerAndGuardTests(unittest.TestCase):
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
        self.db.query(JobRun).filter(JobRun.company_name == "TEST_GUARD").delete()
        self.db.commit()
        self.db.close()

    def test_scheduler_config_endpoints(self):
        response = self.client.patch(
            "/api/jobs/scheduler/config",
            json={
                "enabled": True,
                "poll_seconds": 20,
                "pipeline_interval_minutes": 180,
                "webwatch_interval_minutes": 45,
                "digest_hour_utc": 2,
                "digest_minute_utc": 15,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["poll_seconds"], 20)
        self.assertEqual(payload["pipeline_interval_minutes"], 180)
        self.assertEqual(payload["webwatch_interval_minutes"], 45)
        self.assertEqual(payload["digest_hour_utc"], 2)
        self.assertEqual(payload["digest_minute_utc"], 15)

        status_resp = self.client.get("/api/jobs/scheduler/status")
        self.assertEqual(status_resp.status_code, 200)
        self.assertIn("enabled", status_resp.json())

    def test_scheduler_tick_endpoint(self):
        with patch("app.api.jobs.scheduler_tick", return_value={"enabled": True, "triggers": []}):
            response = self.client.post("/api/jobs/scheduler/tick")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["enabled"], True)

    def test_run_all_direct_blocked_when_active(self):
        run = JobRun(
            run_id=uuid.uuid4().hex,
            trigger_type="PIPELINE_ALL",
            mode="DIRECT",
            status="RUNNING",
            company_name="TEST_GUARD",
        )
        self.db.add(run)
        self.db.commit()

        response = self.client.post("/api/jobs/run-all-direct")
        self.assertEqual(response.status_code, 409)
        self.assertIn("already active", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
