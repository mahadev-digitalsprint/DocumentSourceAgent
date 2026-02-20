"""Domain-level crawl pacing and cooldown control."""
from __future__ import annotations

import threading
import time
from collections import defaultdict


class DomainControl:
    def __init__(self):
        self._lock = threading.Lock()
        self._last_request_at = defaultdict(float)
        self._blocked_until = defaultdict(float)

    def wait_turn(self, domain: str, min_delay_seconds: float) -> None:
        if min_delay_seconds <= 0:
            return
        with self._lock:
            now = time.time()
            last = self._last_request_at.get(domain, 0.0)
            sleep_for = (last + min_delay_seconds) - now
        if sleep_for > 0:
            time.sleep(sleep_for)
        with self._lock:
            self._last_request_at[domain] = time.time()

    def is_blocked(self, domain: str) -> bool:
        with self._lock:
            return time.time() < self._blocked_until.get(domain, 0.0)

    def mark_blocked(self, domain: str, cooldown_seconds: int) -> None:
        if cooldown_seconds <= 0:
            return
        with self._lock:
            self._blocked_until[domain] = max(self._blocked_until.get(domain, 0.0), time.time() + cooldown_seconds)

    def unblock(self, domain: str) -> None:
        with self._lock:
            self._blocked_until.pop(domain, None)

    def blocked_domains(self) -> list[dict]:
        now = time.time()
        rows = []
        with self._lock:
            for domain, blocked_until in self._blocked_until.items():
                if blocked_until <= now:
                    continue
                rows.append(
                    {
                        "domain": domain,
                        "blocked_until_epoch": blocked_until,
                        "remaining_seconds": round(blocked_until - now, 2),
                    }
                )
        rows.sort(key=lambda row: row["remaining_seconds"], reverse=True)
        return rows

    def clear(self) -> None:
        with self._lock:
            self._last_request_at.clear()
            self._blocked_until.clear()


domain_control = DomainControl()
