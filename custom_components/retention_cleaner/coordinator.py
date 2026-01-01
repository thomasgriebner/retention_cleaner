from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, time as dt_time
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BASE_PATH,
    CONF_PATTERN,
    CONF_RETENTION_DAYS,
    CONF_RUN_AT,
    CONF_DRY_RUN,
    CONF_MAX_DELETES,
    COORDINATOR_UPDATE_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ScanResult:
    total_files: int
    older_than_retention: int
    path_available: bool


@dataclass
class CleanupResult:
    deleted: int
    total_after: int
    older_remaining: int
    path_available: bool


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_run_at(value: str) -> dt_time:
    hh, mm = (value or "03:15").split(":")
    return dt_time(hour=int(hh), minute=int(mm), second=0)


def _scan_folder(base_path: str, pattern: str, retention_days: int) -> ScanResult:
    base = Path(base_path)

    if not base.exists() or not base.is_dir():
        return ScanResult(total_files=0, older_than_retention=0, path_available=False)

    cutoff_ts = datetime.now().timestamp() - (retention_days * 24 * 60 * 60)

    total = 0
    older = 0

    try:
        for p in base.glob(pattern):
            if not p.is_file():
                continue

            total += 1
            try:
                if p.stat().st_mtime < cutoff_ts:
                    older += 1
            except OSError:
                # Cannot stat file → keep it counted, ignore age
                pass
    except Exception as e:
        raise RuntimeError(str(e)) from e

    return ScanResult(total_files=total, older_than_retention=older, path_available=True)


def _cleanup_folder(
    base_path: str,
    pattern: str,
    retention_days: int,
    dry_run: bool,
    max_deletes: int,
) -> CleanupResult:
    base = Path(base_path)

    if not base.exists() or not base.is_dir():
        return CleanupResult(deleted=0, total_after=0, older_remaining=0, path_available=False)

    cutoff_ts = datetime.now().timestamp() - (retention_days * 24 * 60 * 60)

    deleted = 0
    total_after = 0
    older_remaining = 0

    try:
        for p in base.glob(pattern):
            if not p.is_file():
                continue

            try:
                mtime = p.stat().st_mtime
            except OSError:
                # can't stat -> keep file, count as remaining
                total_after += 1
                continue

            if mtime < cutoff_ts:
                # file is older than retention
                if dry_run or deleted >= max_deletes:
                    # keep it (dry run / cap reached)
                    total_after += 1
                    older_remaining += 1
                    continue

                try:
                    p.unlink()
                    deleted += 1
                    # deleted -> not remaining
                except OSError:
                    # couldn't delete -> remains
                    total_after += 1
                    older_remaining += 1
            else:
                # file is within retention
                total_after += 1

    except Exception as e:
        raise RuntimeError(str(e)) from e

    return CleanupResult(
        deleted=deleted,
        total_after=total_after,
        older_remaining=older_remaining,
        path_available=True,
    )


class RetentionCleanerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        # Visible runtime state for dashboard (separated!)
        self.deleted_last_run: int = 0
        self.last_scan: str = "-"
        self.last_cleanup: str = "-"

        self._unsub_daily = None

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"retention_cleaner_{entry.entry_id}",
            update_interval=timedelta(seconds=COORDINATOR_UPDATE_INTERVAL_SECONDS),
        )

    @property
    def cfg(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    @property
    def base_path(self) -> str:
        return self.cfg[CONF_BASE_PATH]

    @property
    def pattern(self) -> str:
        return self.cfg[CONF_PATTERN]

    @property
    def retention_days(self) -> int:
        return int(self.cfg[CONF_RETENTION_DAYS])

    @property
    def dry_run(self) -> bool:
        return bool(self.cfg.get(CONF_DRY_RUN, False))

    @property
    def max_deletes(self) -> int:
        return int(self.cfg.get(CONF_MAX_DELETES, 5000))

    @property
    def run_at(self) -> dt_time:
        return _parse_run_at(self.cfg.get(CONF_RUN_AT, "03:15"))

    async def async_setup_daily_schedule(self) -> None:
        """Schedule the daily cleanup run based on config."""
        self.async_remove_listeners()

        t = self.run_at

        @callback
        async def _run_daily(now: datetime) -> None:
            await self.async_run_cleanup_now(triggered_by="schedule")

        self._unsub_daily = async_track_time_change(
            self.hass,
            _run_daily,
            hour=t.hour,
            minute=t.minute,
            second=0,
        )

    def async_remove_listeners(self) -> None:
        """Remove scheduler listeners (called on unload)."""
        if self._unsub_daily:
            self._unsub_daily()
            self._unsub_daily = None

    async def async_run_scan_now(self) -> None:
        """Manual scan refresh (no deletion)."""
        self.last_scan = _now_iso()
        await self.async_request_refresh()

    async def async_run_cleanup_now(self, triggered_by: str = "manual") -> None:
        """Manual or scheduled cleanup run (deletes files older than retention)."""
        # Mark intent/time first so the dashboard shows something even if scan later fails
        self.last_cleanup = _now_iso()

        try:
            result: CleanupResult = await asyncio.to_thread(
                _cleanup_folder,
                self.base_path,
                self.pattern,
                self.retention_days,
                self.dry_run,
                self.max_deletes,
            )
        except Exception as e:
            # keep last_cleanup timestamp, but expose error via coordinator failure
            raise UpdateFailed(str(e)) from e

        # Update visible state
        self.deleted_last_run = result.deleted

        # Refresh counts after cleanup
        await self.async_request_refresh()

        _LOGGER.info(
            "Retention Cleaner cleanup run (%s): deleted=%s dry_run=%s max_deletes=%s base_path=%s",
            triggered_by,
            result.deleted,
            self.dry_run,
            self.max_deletes,
            self.base_path,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        # Any refresh means: we updated the values
        self.last_scan = _now_iso()

        try:
            result: ScanResult = await asyncio.to_thread(
                _scan_folder,
                self.base_path,
                self.pattern,
                self.retention_days,
            )
        except Exception as e:
            raise UpdateFailed(str(e)) from e

        return {
            "base_path": self.base_path,
            "pattern": self.pattern,
            "retention_days": self.retention_days,
            "dry_run": self.dry_run,
            "max_deletes": self.max_deletes,
            "run_at": self.cfg.get(CONF_RUN_AT, "03:15"),
            "path_available": result.path_available,
            "total_files": result.total_files,
            "older_than_retention": result.older_than_retention,
            "deleted_last_run": self.deleted_last_run,
            "last_scan": self.last_scan,
            "last_cleanup": self.last_cleanup,
        }