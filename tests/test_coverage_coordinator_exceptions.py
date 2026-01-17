"""Test coverage for coordinator exception handlers."""

from __future__ import annotations

import asyncio
import os
import time as time_module
from unittest.mock import Mock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.retention_cleaner.coordinator import RetentionCleanerCoordinator


async def test_scheduled_cleanup_callback_triggers_cleanup(
    hass: HomeAssistant, tmp_path
):
    """Test that scheduled time change callback (lines 527-528) triggers cleanup."""
    media_dir = tmp_path / "media" / "scheduled"
    media_dir.mkdir(parents=True)

    entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Scheduled Test",
        data={
            "base_path": str(media_dir),
            "pattern": "*.test",
            "retention_days": 5,
            "dry_run": False,
            "max_deletes": 100,
            "run_at": "03:00",
        },
        entry_id="test_scheduled_callback",
    )
    entry.add_to_hass(hass)

    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        # Create old files to be deleted
        for i in range(3):
            test_file = media_dir / f"old_{i}.test"
            test_file.write_text(f"test data {i}")
            old_time = time_module.time() - (7 * 24 * 60 * 60)
            os.utime(test_file, (old_time, old_time))

        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Set up the schedule
        await coordinator.async_setup_daily_schedule()

        # Find the callback that was registered
        # The callback is stored in coordinator._unsub_daily
        assert coordinator._unsub_daily is not None

        # Manually trigger the scheduled callback by simulating time change
        # The callback is _run_daily which is internal, but we can trigger it
        # by calling async_run_cleanup_now with triggered_by="schedule"
        # However, to actually test lines 527-528, we need to simulate the
        # async_track_time_change trigger.

        # Get the current time from dt_util

        # Patch async_track_time_change to capture the callback
        captured_callback = None

        def capture_callback(hass, action, hour=None, minute=None, second=None):
            nonlocal captured_callback
            captured_callback = action
            return Mock()  # Return a mock unsubscribe function

        with patch(
            "custom_components.retention_cleaner.coordinator.async_track_time_change",
            side_effect=capture_callback,
        ):
            await coordinator.async_setup_daily_schedule()

        # Now trigger the captured callback directly
        assert captured_callback is not None
        await captured_callback(dt_util.utcnow())
        await hass.async_block_till_done()

        # Verify cleanup was triggered
        assert coordinator.deleted_last_run == 3

        remaining_files = list(media_dir.glob("*.test"))
        assert len(remaining_files) == 0

    finally:
        await coordinator.async_shutdown()


async def test_async_update_data_generic_exception_handler(
    hass: HomeAssistant, tmp_path
):
    """Test generic exception handler in _async_update_data (lines 680-681)."""
    media_dir = tmp_path / "media" / "exception_test"
    media_dir.mkdir(parents=True)

    entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Exception Test",
        data={
            "base_path": str(media_dir),
            "pattern": "*.test",
            "retention_days": 7,
            "dry_run": True,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_exception_handler",
    )
    entry.add_to_hass(hass)

    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        # Mock asyncio.to_thread to raise a non-RuntimeError, non-OSError exception
        # This will bypass _scan_folder's exception handlers and hit the
        # generic exception handler in _async_update_data (lines 680-681)
        async def raise_type_error(*args, **kwargs):
            raise TypeError("Simulated async operation error")

        with patch("asyncio.to_thread", side_effect=raise_type_error):
            with pytest.raises(UpdateFailed) as exc_info:
                # Call _async_update_data directly to get the exception
                await coordinator._async_update_data()

            error_msg = str(exc_info.value).lower()
            assert (
                "simulated async operation error" in error_msg
                or "typeerror" in error_msg
            )

    finally:
        await coordinator.async_shutdown()


async def test_async_run_cleanup_now_generic_exception_handler(
    hass: HomeAssistant, tmp_path
):
    """Test generic exception handler in async_run_cleanup_now (lines 616-619)."""
    media_dir = tmp_path / "media" / "cleanup_exception"
    media_dir.mkdir(parents=True)

    entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Cleanup Exception Test",
        data={
            "base_path": str(media_dir),
            "pattern": "*.test",
            "retention_days": 7,
            "dry_run": False,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_cleanup_exception",
    )
    entry.add_to_hass(hass)

    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        from custom_components.retention_cleaner.coordinator import _cleanup_folder

        # Mock _cleanup_folder to raise a non-RuntimeError exception
        # This should be caught by the generic Exception handler (lines 616-619)
        async def raise_value_error(*args, **kwargs):
            func = args[0]
            if func == _cleanup_folder:
                raise ValueError("Simulated cleanup error")
            return await asyncio.to_thread(func, *args[1:], **kwargs)

        with patch("asyncio.to_thread", side_effect=raise_value_error):
            with pytest.raises(UpdateFailed) as exc_info:
                await coordinator.async_run_cleanup_now("manual")

            error_msg = str(exc_info.value).lower()
            assert "simulated cleanup error" in error_msg or "valueerror" in error_msg

    finally:
        await coordinator.async_shutdown()
