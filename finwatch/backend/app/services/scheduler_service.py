"""Local scheduler loop backed by DB-stored settings."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.config import get_settings
from app.database import SessionLocal
from app.models import SystemSetting
from app.services.job_run_service import create_job_run, mark_failed
from app.services.run_guard import acquire_singleflight, has_active_run
from app.utils.time import utc_now_naive

logger = logging.getLogger(__name__)
settings = get_settings()


def _to_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value: Optional[str], default: int) -> int:
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _get_setting(db, key: str, default: Optional[str] = None) -> Optional[str]:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row is None:
        return default
    return row.value


def _set_setting(db, key: str, value: str) -> None:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row is None:
        row = SystemSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value


@dataclass
class SchedulerConfig:
    enabled: bool
    poll_seconds: int
    pipeline_interval_minutes: int
    webwatch_interval_minutes: int
    digest_hour_utc: int
    digest_minute_utc: int


def load_scheduler_config() -> SchedulerConfig:
    db = SessionLocal()
    try:
        enabled = _to_bool(_get_setting(db, "scheduler_enabled", str(settings.scheduler_enabled)), settings.scheduler_enabled)
        poll_seconds = _to_int(_get_setting(db, "scheduler_poll_seconds", str(settings.scheduler_poll_seconds)), settings.scheduler_poll_seconds)
        pipeline_interval = _to_int(
            _get_setting(db, "scheduler_pipeline_interval_minutes", str(settings.scheduler_pipeline_interval_minutes)),
            settings.scheduler_pipeline_interval_minutes,
        )
        webwatch_interval = _to_int(
            _get_setting(db, "scheduler_webwatch_interval_minutes", str(settings.scheduler_webwatch_interval_minutes)),
            settings.scheduler_webwatch_interval_minutes,
        )
        digest_hour = _to_int(
            _get_setting(db, "scheduler_digest_hour_utc", str(settings.scheduler_digest_hour_utc)),
            settings.scheduler_digest_hour_utc,
        )
        digest_minute = _to_int(
            _get_setting(db, "scheduler_digest_minute_utc", str(settings.scheduler_digest_minute_utc)),
            settings.scheduler_digest_minute_utc,
        )

        return SchedulerConfig(
            enabled=enabled,
            poll_seconds=max(5, min(poll_seconds, 300)),
            pipeline_interval_minutes=max(15, min(pipeline_interval, 24 * 60)),
            webwatch_interval_minutes=max(5, min(webwatch_interval, 24 * 60)),
            digest_hour_utc=max(0, min(digest_hour, 23)),
            digest_minute_utc=max(0, min(digest_minute, 59)),
        )
    finally:
        db.close()


def _parse_last_run(value: Optional[str]):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _queue_trigger(db, *, trigger_type: str):
    try:
        if trigger_type == "PIPELINE_ALL":
            from app.tasks import run_all_companies

            run = create_job_run(db, trigger_type="PIPELINE_ALL", mode="QUEUED", status="QUEUED", company_name="ALL_ACTIVE_COMPANIES")
            task = run_all_companies.delay(run.run_id)
        elif trigger_type == "WEBWATCH":
            from app.tasks import run_hourly_webwatch

            run = create_job_run(db, trigger_type="WEBWATCH", mode="QUEUED", status="QUEUED", company_name="ALL_ACTIVE_COMPANIES")
            task = run_hourly_webwatch.delay(run.run_id)
        else:
            from app.tasks import run_daily_digest

            run = create_job_run(db, trigger_type="DIGEST", mode="QUEUED", status="QUEUED", company_name="ALL_ACTIVE_COMPANIES")
            task = run_daily_digest.delay(run.run_id)

        run.celery_job_id = task.id
        db.commit()
        return run.run_id
    except Exception as exc:
        if "run" in locals():
            mark_failed(db, run.run_id, str(exc))
        raise


def scheduler_status() -> dict:
    config = load_scheduler_config()
    db = SessionLocal()
    try:
        return {
            "enabled": config.enabled,
            "poll_seconds": config.poll_seconds,
            "pipeline_interval_minutes": config.pipeline_interval_minutes,
            "webwatch_interval_minutes": config.webwatch_interval_minutes,
            "digest_hour_utc": config.digest_hour_utc,
            "digest_minute_utc": config.digest_minute_utc,
            "last_tick_at": _get_setting(db, "scheduler_last_tick_at"),
            "last_pipeline_run_at": _get_setting(db, "scheduler_last_pipeline_run_at"),
            "last_webwatch_run_at": _get_setting(db, "scheduler_last_webwatch_run_at"),
            "last_digest_run_at": _get_setting(db, "scheduler_last_digest_run_at"),
            "last_error": _get_setting(db, "scheduler_last_error"),
        }
    finally:
        db.close()


def update_scheduler_config(data: dict) -> dict:
    db = SessionLocal()
    try:
        if "enabled" in data:
            _set_setting(db, "scheduler_enabled", "true" if bool(data["enabled"]) else "false")
        if "poll_seconds" in data:
            _set_setting(db, "scheduler_poll_seconds", str(int(data["poll_seconds"])))
        if "pipeline_interval_minutes" in data:
            _set_setting(db, "scheduler_pipeline_interval_minutes", str(int(data["pipeline_interval_minutes"])))
        if "webwatch_interval_minutes" in data:
            _set_setting(db, "scheduler_webwatch_interval_minutes", str(int(data["webwatch_interval_minutes"])))
        if "digest_hour_utc" in data:
            _set_setting(db, "scheduler_digest_hour_utc", str(int(data["digest_hour_utc"])))
        if "digest_minute_utc" in data:
            _set_setting(db, "scheduler_digest_minute_utc", str(int(data["digest_minute_utc"])))
        db.commit()
    finally:
        db.close()
    return scheduler_status()


def scheduler_tick() -> dict:
    config = load_scheduler_config()
    now = utc_now_naive()
    triggers = []

    db = SessionLocal()
    try:
        _set_setting(db, "scheduler_last_tick_at", now.isoformat())
        _set_setting(db, "scheduler_last_error", "")
        if not config.enabled:
            db.commit()
            return {"enabled": False, "triggers": []}

        pipeline_last = _parse_last_run(_get_setting(db, "scheduler_last_pipeline_run_at"))
        if pipeline_last is None:
            _set_setting(db, "scheduler_last_pipeline_run_at", now.isoformat())
        elif now - pipeline_last >= timedelta(minutes=config.pipeline_interval_minutes) and not has_active_run(
            db, trigger_types=["PIPELINE", "PIPELINE_ALL"]
        ):
            run_id = _queue_trigger(db, trigger_type="PIPELINE_ALL")
            _set_setting(db, "scheduler_last_pipeline_run_at", now.isoformat())
            triggers.append({"trigger_type": "PIPELINE_ALL", "run_id": run_id})

        webwatch_last = _parse_last_run(_get_setting(db, "scheduler_last_webwatch_run_at"))
        if webwatch_last is None:
            _set_setting(db, "scheduler_last_webwatch_run_at", now.isoformat())
        elif now - webwatch_last >= timedelta(minutes=config.webwatch_interval_minutes) and not has_active_run(
            db, trigger_types=["WEBWATCH"]
        ):
            run_id = _queue_trigger(db, trigger_type="WEBWATCH")
            _set_setting(db, "scheduler_last_webwatch_run_at", now.isoformat())
            triggers.append({"trigger_type": "WEBWATCH", "run_id": run_id})

        digest_last = _parse_last_run(_get_setting(db, "scheduler_last_digest_run_at"))
        if digest_last is None:
            _set_setting(db, "scheduler_last_digest_run_at", now.isoformat())
            digest_last = now
        due_digest_time = now.replace(
            hour=config.digest_hour_utc,
            minute=config.digest_minute_utc,
            second=0,
            microsecond=0,
        )
        digest_due = now >= due_digest_time and (digest_last is None or digest_last < due_digest_time)
        if digest_due and not has_active_run(db, trigger_types=["DIGEST"]):
            run_id = _queue_trigger(db, trigger_type="DIGEST")
            _set_setting(db, "scheduler_last_digest_run_at", now.isoformat())
            triggers.append({"trigger_type": "DIGEST", "run_id": run_id})

        db.commit()
        return {"enabled": True, "triggers": triggers}
    except Exception as exc:
        db.rollback()
        try:
            _set_setting(db, "scheduler_last_error", str(exc)[:1000])
            db.commit()
        except Exception:
            db.rollback()
        logger.exception("[SCHEDULER] Tick failed: %s", exc)
        return {"enabled": config.enabled, "triggers": triggers, "error": str(exc)}
    finally:
        db.close()


class LocalSchedulerLoop:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="finwatch-scheduler", daemon=True)
        self._thread.start()
        logger.info("[SCHEDULER] Local scheduler loop started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("[SCHEDULER] Local scheduler loop stopped")

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                with acquire_singleflight("scheduler-tick"):
                    scheduler_tick()
            except Exception:
                # If lock is busy or tick fails, skip this cycle.
                pass
            poll_seconds = load_scheduler_config().poll_seconds
            time.sleep(max(5, min(poll_seconds, 300)))


scheduler_loop = LocalSchedulerLoop()
