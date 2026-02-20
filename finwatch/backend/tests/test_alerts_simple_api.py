import unittest

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import EmailSetting


class AlertsSimpleApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    def setUp(self):
        self.db = SessionLocal()
        self.db.query(EmailSetting).delete()
        self.db.commit()

    def tearDown(self):
        self.db.query(EmailSetting).delete()
        self.db.commit()
        self.db.close()

    def test_simple_config_save_and_get(self):
        response = self.client.post(
            "/api/alerts/simple",
            json={"receiver_email": "ops@example.com", "send_on_change": True, "daily_digest_hour": 6},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["saved"])
        self.assertEqual(payload["receiver_email"], "ops@example.com")

        get_response = self.client.get("/api/alerts/simple")
        self.assertEqual(get_response.status_code, 200)
        cfg = get_response.json()
        self.assertEqual(cfg["receiver_email"], "ops@example.com")
        self.assertTrue(cfg["configured"])

    def test_simple_config_rejects_invalid_email(self):
        response = self.client.post(
            "/api/alerts/simple",
            json={"receiver_email": "invalid-email"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "INVALID_EMAIL")


if __name__ == "__main__":
    unittest.main()
