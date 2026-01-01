import logging
_LOGGER = logging.getLogger(__name__)

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BASE_PATH,
    CONF_PATTERN,
    CONF_RETENTION_DAYS,
    COORDINATOR_UPDATE_INTERVAL_SECONDS,
)


@dataclass
class ScanResult:
    total_files: int
    older_than_retention: int
    path_available: bool


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
                # can't stat -> ignore age, but keep total
                pass
    except Exception as e:
        raise RuntimeError(str(e)) from e

    return ScanResult(total_files=total, older_than_retention=older, path_available=True)


class RetentionCleanerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        # These are placeholders until Step 5 (real cleanup)
        self.deleted_last_run: int = 0
        self.last_run: str = "-"

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

    async def async_run_scan_now(self) -> None:
        """Manual scan refresh (no deletion)."""
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
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
            "path_available": result.path_available,
            "total_files": result.total_files,
            "older_than_retention": result.older_than_retention,
            "deleted_last_run": self.deleted_last_run,
            "last_run": self.last_run,
        }
