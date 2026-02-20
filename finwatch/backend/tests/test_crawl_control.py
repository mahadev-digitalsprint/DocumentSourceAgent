import time
import unittest

from app.utils.crawl_control import DomainControl


class CrawlControlTests(unittest.TestCase):
    def test_wait_turn_enforces_domain_delay(self):
        control = DomainControl()
        control.wait_turn("example.com", 0.03)

        started = time.time()
        control.wait_turn("example.com", 0.03)
        elapsed = time.time() - started

        self.assertGreaterEqual(elapsed, 0.02)

    def test_block_lifecycle(self):
        control = DomainControl()
        domain = "blocked.example"

        control.mark_blocked(domain, 10)
        self.assertTrue(control.is_blocked(domain))
        snapshot = control.blocked_domains()
        self.assertTrue(any(row["domain"] == domain for row in snapshot))

        control.unblock(domain)
        self.assertFalse(control.is_blocked(domain))
        self.assertFalse(any(row["domain"] == domain for row in control.blocked_domains()))


if __name__ == "__main__":
    unittest.main()
