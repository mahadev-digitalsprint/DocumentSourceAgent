"""Time utilities."""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now_naive() -> datetime:
    """Return current UTC timestamp as naive datetime for DB compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
