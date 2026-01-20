"""Test max_files_in_folder exception handling during Step 5."""

import errno
from pathlib import Path
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest

from custom_components.retention_cleaner.coordinator import RetentionCleanerCoordinator
from tests.conftest import TEST_FILE_AGE_NEW, TEST_FILE_COUNT_MEDIUM


async def test_max_files_file_not_found_race_condition(
    hass: HomeAssistant, tmp_path, create_numbered_files, mock_max_files_config
):
    """Test FileNotFoundError handling during Step 5 deletion."""
    media_dir = tmp_path / "media" / "test"
    max_files_limit = 10

    create_numbered_files(
        media_dir, count=TEST_FILE_COUNT_MEDIUM, age_days=TEST_FILE_AGE_NEW
    )
    mock_entry = mock_max_files_config(
        base_path=str(media_dir),
        max_files=max_files_limit,
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        original_unlink = Path.unlink

        def unlink_with_race_condition(self, *args, **kwargs):
            if self.name == "file_00.jpg":
                raise FileNotFoundError(f"File not found: {self}")
            return original_unlink(self, *args, **kwargs)

        with patch.object(Path, "unlink", unlink_with_race_condition):
            await coordinator.async_run_cleanup_now()
            await hass.async_block_till_done()

            if coordinator.data is None:
                await coordinator.async_refresh()
                await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"
        assert (
            result["deleted_last_run"] >= max_files_limit - 1
        ), "Should handle FileNotFoundError and continue deletion"
        assert (
            result["total_files"] <= max_files_limit + 1
        ), "Should reach target despite race condition"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_file_not_found_old_file_race_condition(
    hass: HomeAssistant, tmp_path, mock_max_files_config
):
    """Test FileNotFoundError for old file during Step 5 deletion (updates older_remaining).

    Scenario: Old files are protected by keep_minimum_files in Step 4, but need deletion in Step 5.
    One old file (file_02.jpg) triggers FileNotFoundError during Step 5, requiring older_remaining decrement.
    """
    import os
    import time as time_module

    from tests.conftest import TEST_FILE_AGE_OLD

    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)
    max_files_limit = 3
    keep_minimum = 8
    old_file_count = 10

    for i in range(old_file_count):
        file = media_dir / f"file_{i:02d}.jpg"
        file.write_text(f"content {i}")
        old_time = time_module.time() - (TEST_FILE_AGE_OLD * 24 * 60 * 60)
        os.utime(file, (old_time, old_time))

    mock_entry = mock_max_files_config(
        base_path=str(media_dir),
        max_files=max_files_limit,
        keep_minimum=keep_minimum,
        retention_days=7,
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        original_unlink = Path.unlink
        file_not_found_triggered = False

        def unlink_with_old_file_race_condition(self, *args, **kwargs):
            nonlocal file_not_found_triggered
            if self.name == "file_02.jpg" and not file_not_found_triggered:
                file_not_found_triggered = True
                raise FileNotFoundError(f"File not found: {self}")
            return original_unlink(self, *args, **kwargs)

        with patch.object(Path, "unlink", unlink_with_old_file_race_condition):
            await coordinator.async_run_cleanup_now()
            await hass.async_block_till_done()

            if coordinator.data is None:
                await coordinator.async_refresh()
                await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"
        assert (
            file_not_found_triggered
        ), "Should trigger FileNotFoundError for old protected file during Step 5"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_permission_error_during_step5(
    hass: HomeAssistant, tmp_path, create_numbered_files, mock_max_files_config
):
    """Test PermissionError handling during Step 5 deletion."""
    media_dir = tmp_path / "media" / "test"
    max_files_limit = 10

    create_numbered_files(
        media_dir, count=TEST_FILE_COUNT_MEDIUM, age_days=TEST_FILE_AGE_NEW
    )
    mock_entry = mock_max_files_config(
        base_path=str(media_dir),
        max_files=max_files_limit,
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        original_unlink = Path.unlink
        permission_error_triggered = False

        def unlink_with_permission_error(self, *args, **kwargs):
            nonlocal permission_error_triggered
            if self.name == "file_00.jpg" and not permission_error_triggered:
                permission_error_triggered = True
                raise PermissionError("Permission denied")
            return original_unlink(self, *args, **kwargs)

        with patch.object(Path, "unlink", unlink_with_permission_error):
            await coordinator.async_run_cleanup_now()
            await hass.async_block_till_done()

            if coordinator.data is None:
                await coordinator.async_refresh()
                await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"
        assert permission_error_triggered, "Should trigger PermissionError"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_disk_full_during_step5(
    hass: HomeAssistant, tmp_path, create_numbered_files, mock_max_files_config
):
    """Test disk full error handling during Step 5 deletion."""
    media_dir = tmp_path / "media" / "test"
    max_files_limit = 10

    create_numbered_files(
        media_dir, count=TEST_FILE_COUNT_MEDIUM, age_days=TEST_FILE_AGE_NEW
    )
    mock_entry = mock_max_files_config(
        base_path=str(media_dir),
        max_files=max_files_limit,
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        original_unlink = Path.unlink
        disk_full_triggered = False

        def unlink_with_disk_full(self, *args, **kwargs):
            nonlocal disk_full_triggered
            if self.name == "file_00.jpg" and not disk_full_triggered:
                disk_full_triggered = True
                err = OSError("No space left on device")
                err.errno = errno.ENOSPC
                raise err
            return original_unlink(self, *args, **kwargs)

        with patch.object(Path, "unlink", unlink_with_disk_full):
            try:
                await coordinator.async_run_cleanup_now()
                await hass.async_block_till_done()
                pytest.fail("Should have raised an exception due to disk full")
            except (UpdateFailed, HomeAssistantError, RuntimeError) as exc:
                error_msg = str(exc).lower()
                assert (
                    "disk" in error_msg or "cleanup failed" in error_msg
                ), f"Should indicate disk/cleanup issue, got: {exc}"

        assert disk_full_triggered, "Should trigger disk full error"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_readonly_filesystem_during_step5(
    hass: HomeAssistant, tmp_path, create_numbered_files, mock_max_files_config
):
    """Test read-only filesystem error handling during Step 5 deletion."""
    media_dir = tmp_path / "media" / "test"
    max_files_limit = 10

    create_numbered_files(
        media_dir, count=TEST_FILE_COUNT_MEDIUM, age_days=TEST_FILE_AGE_NEW
    )
    mock_entry = mock_max_files_config(
        base_path=str(media_dir),
        max_files=max_files_limit,
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        original_unlink = Path.unlink
        readonly_triggered = False

        def unlink_with_readonly(self, *args, **kwargs):
            nonlocal readonly_triggered
            if self.name == "file_00.jpg" and not readonly_triggered:
                readonly_triggered = True
                err = OSError("Read-only file system")
                err.errno = errno.EROFS
                raise err
            return original_unlink(self, *args, **kwargs)

        with patch.object(Path, "unlink", unlink_with_readonly):
            try:
                await coordinator.async_run_cleanup_now()
                await hass.async_block_till_done()
                pytest.fail(
                    "Should have raised an exception due to read-only filesystem"
                )
            except (UpdateFailed, HomeAssistantError, RuntimeError) as exc:
                error_msg = str(exc).lower()
                assert (
                    "read-only" in error_msg
                    or "readonly" in error_msg
                    or "cleanup failed" in error_msg
                ), f"Should indicate read-only/cleanup issue, got: {exc}"

        assert readonly_triggered, "Should trigger read-only filesystem error"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_generic_oserror_during_step5(
    hass: HomeAssistant, tmp_path, create_numbered_files, mock_max_files_config
):
    """Test generic OSError handling during Step 5 deletion."""
    media_dir = tmp_path / "media" / "test"
    max_files_limit = 10

    create_numbered_files(
        media_dir, count=TEST_FILE_COUNT_MEDIUM, age_days=TEST_FILE_AGE_NEW
    )
    mock_entry = mock_max_files_config(
        base_path=str(media_dir),
        max_files=max_files_limit,
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        original_unlink = Path.unlink
        generic_error_triggered = False

        def unlink_with_generic_error(self, *args, **kwargs):
            nonlocal generic_error_triggered
            if self.name == "file_00.jpg" and not generic_error_triggered:
                generic_error_triggered = True
                err = OSError("Generic file system error")
                err.errno = errno.EIO
                raise err
            return original_unlink(self, *args, **kwargs)

        with patch.object(Path, "unlink", unlink_with_generic_error):
            await coordinator.async_run_cleanup_now()
            await hass.async_block_till_done()

            if coordinator.data is None:
                await coordinator.async_refresh()
                await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"
        assert generic_error_triggered, "Should trigger generic OSError"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()
