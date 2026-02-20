import unittest
from unittest.mock import patch

import httpx

from app.utils.http_client import is_blocked_response, request_with_retries


class HttpClientUtilsTests(unittest.TestCase):
    def test_is_blocked_response_by_status(self):
        response = httpx.Response(403, text="forbidden")
        self.assertTrue(is_blocked_response(response))

    def test_is_blocked_response_by_content(self):
        response = httpx.Response(200, text="Please complete captcha to continue")
        self.assertTrue(is_blocked_response(response))

    def test_request_with_retries_recovers_after_retry_status(self):
        first = httpx.Response(503, text="temporary unavailable")
        second = httpx.Response(200, text="ok")
        with patch("app.utils.http_client.httpx.request", side_effect=[first, second]) as mocked, patch(
            "app.utils.http_client.time.sleep", return_value=None
        ):
            response = request_with_retries("GET", "https://example.test", retries=2)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(mocked.call_count, 2)

    def test_request_with_retries_raises_on_transport_failure(self):
        with patch(
            "app.utils.http_client.httpx.request",
            side_effect=httpx.ConnectError("connect error"),
        ), patch("app.utils.http_client.time.sleep", return_value=None):
            with self.assertRaises(httpx.ConnectError):
                request_with_retries("GET", "https://example.test", retries=2)


if __name__ == "__main__":
    unittest.main()
