"""Test the retention_cleaner coordinator."""

import errno
import os
from pathlib import Path
import time as time_module
from unittest.mock import Mock, patch

from homeassistant.core import HomeAssistant
import pytest

from custom_components.retention_cleaner.coordinator import RetentionCleanerCoordinator


async def test_coordinator_setup(hass: HomeAssistant, mock_setup_entry):
    """Test coordinator initialization."""
    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry)

    assert coordinator.base_path == "/media/test"
    assert coordinator.pattern == "*.jpg"
    assert coordinator.retention_days == 7
    assert coordinator.dry_run is True
    assert coordinator.max_deletes == 100
    assert coordinator.schedule_time == "02:00"
    assert coordinator.name == "Test Cleanup"


async def test_coordinator_scan_with_real_files(
    hass: HomeAssistant, mock_setup_entry, tmp_path
):
    """Test scanning files with real file operations."""
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)

    mock_setup_entry.data = {
        **mock_setup_entry.data,
        "base_path": str(media_dir),
    }

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry)

    for i in range(10):
        file = media_dir / f"test_{i}.jpg"
        file.touch()
        if i < 5:
            # Make 5 files old (8 days)
            old_time = time_module.time() - (8 * 24 * 60 * 60)
            os.utime(file, (old_time, old_time))

    (media_dir / "test.txt").touch()
    (media_dir / "other.png").touch()

    result = await coordinator.async_scan_now()

    assert result["total_files"] == 10  # Only .jpg files
    assert result["older_than_retention"] == 5
    assert result["path_accessible"] is True


async def test_coordinator_cleanup_dry_run_real_files(
    hass: HomeAssistant, mock_setup_entry, tmp_path
):
    """Test cleanup in dry run mode with real files - should not delete."""
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)

    mock_setup_entry.data = {
        **mock_setup_entry.data,
        "base_path": str(media_dir),
        "dry_run": True,
    }

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry)

    test_files = []
    for i in range(5):
        file = media_dir / f"test_{i}.jpg"
        file.touch()
        old_time = time_module.time() - (8 * 24 * 60 * 60)
        os.utime(file, (old_time, old_time))
        test_files.append(file)

    result = await coordinator.async_run_cleanup_now()

    assert result["deleted_last_run"] == 0
    for file in test_files:
        assert file.exists()  # All files should still exist


async def test_coordinator_cleanup_with_deletion_real_files(
    hass: HomeAssistant, mock_setup_entry_no_dry_run, tmp_path
):
    """Test cleanup with actual file deletion."""
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)

    mock_setup_entry_no_dry_run.data = {
        **mock_setup_entry_no_dry_run.data,
        "base_path": str(media_dir),
        "pattern": "*.log",
        "dry_run": False,
    }

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry_no_dry_run)

    test_files = []
    for i in range(5):
        file = media_dir / f"test_{i}.log"
        file.write_text(f"log content {i}")  # Write some content
        old_time = time_module.time() - (4 * 24 * 60 * 60)  # 4 days old
        os.utime(file, (old_time, old_time))
        test_files.append(file)

    result = await coordinator.async_run_cleanup_now()

    assert result["deleted_last_run"] == 5
    assert result["total_files"] == 0
    for file in test_files:
        assert not file.exists()  # All files should be deleted


async def test_coordinator_max_deletes_limit_real_files(
    hass: HomeAssistant, mock_setup_entry_no_dry_run, tmp_path
):
    """Test that max_deletes limit is enforced with real files."""
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)

    mock_setup_entry_no_dry_run.data = {
        **mock_setup_entry_no_dry_run.data,
        "base_path": str(media_dir),
        "pattern": "*.log",
        "dry_run": False,
        "max_deletes": 3,  # Limit to 3 deletions
    }

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry_no_dry_run)

    for i in range(10):
        file = media_dir / f"test_{i}.log"
        file.touch()
        old_time = time_module.time() - (4 * 24 * 60 * 60)
        os.utime(file, (old_time, old_time))

    result = await coordinator.async_run_cleanup_now()

    assert result["deleted_last_run"] == 3

    remaining = list(media_dir.glob("*.log"))
    assert len(remaining) == 7  # 10 - 3 = 7


async def test_coordinator_path_not_accessible(hass: HomeAssistant, mock_setup_entry):
    """Test behavior when path doesn't exist."""
    mock_setup_entry.data = {
        **mock_setup_entry.data,
        "base_path": "/media/nonexistent/path",
    }

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry)

    result = await coordinator._async_update_data()

    assert result["path_accessible"] is False
    assert result["total_files"] == 0
    assert result["older_than_retention"] == 0


async def test_coordinator_race_condition_handling(
    hass: HomeAssistant, mock_setup_entry_no_dry_run, tmp_path
):
    """Test graceful handling of race conditions when file is deleted by another process."""
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)

    mock_setup_entry_no_dry_run.data = {
        **mock_setup_entry_no_dry_run.data,
        "base_path": str(media_dir),
        "pattern": "*.log",
        "dry_run": False,
    }

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry_no_dry_run)

    # Create a file
    test_file = media_dir / "test.log"
    test_file.touch()
    old_time = time_module.time() - (4 * 24 * 60 * 60)
    os.utime(test_file, (old_time, old_time))

    # Mock the unlink to simulate race condition
    original_cleanup = coordinator._cleanup_folder

    def cleanup_with_race(*args, **kwargs):
        # Delete file before cleanup tries to
        if test_file.exists():
            test_file.unlink()
        return original_cleanup(*args, **kwargs)

    with patch.object(coordinator, "_cleanup_folder", side_effect=cleanup_with_race):
        result = await coordinator.async_run_cleanup_now()

    # Should handle gracefully
    assert "error" not in result or result.get("error") is None


async def test_coordinator_schedule_setup(hass: HomeAssistant, mock_setup_entry):
    """Test that daily schedule is set up correctly."""
    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry)

    with patch("homeassistant.helpers.event.async_track_time_change") as mock_track:
        await coordinator.async_setup_daily_schedule()

        # Verify schedule was set up for 02:00
        mock_track.assert_called_once()
        args = mock_track.call_args[0]
        assert args[0] == hass
        assert callable(args[1])
        assert mock_track.call_args[1]["hour"] == 2
        assert mock_track.call_args[1]["minute"] == 0
        assert mock_track.call_args[1]["second"] == 0


async def test_coordinator_unload(hass: HomeAssistant, mock_setup_entry):
    """Test coordinator cleanup on unload."""
    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry)

    # Set up a mock schedule listener
    mock_unsub = Mock()
    coordinator._unsub_daily = mock_unsub

    await coordinator.async_shutdown()

    # Verify listener was removed
    mock_unsub.assert_called_once()
    assert coordinator._unsub_daily is None


async def test_coordinator_performance_tracking(
    hass: HomeAssistant, mock_setup_entry, tmp_path
):
    """Test that scan and cleanup duration are tracked."""
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)

    mock_setup_entry.data = {
        **mock_setup_entry.data,
        "base_path": str(media_dir),
    }

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry)

    # Create some files
    for i in range(5):
        (media_dir / f"test_{i}.jpg").touch()

    # Test scan duration tracking
    result = await coordinator.async_scan_now()
    assert "last_scan_duration_ms" in result
    assert isinstance(result["last_scan_duration_ms"], float)
    assert result["last_scan_duration_ms"] >= 0

    # Test cleanup duration tracking
    result = await coordinator.async_run_cleanup_now()
    assert "last_cleanup_duration_ms" in result
    assert isinstance(result["last_cleanup_duration_ms"], float)
    assert result["last_cleanup_duration_ms"] >= 0


async def test_coordinator_permission_error_mocked(
    hass: HomeAssistant, mock_setup_entry_no_dry_run
):
    """Test handling of permission errors during deletion."""
    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry_no_dry_run)
    coordinator.dry_run = False

    mock_file = Mock(spec=Path)
    mock_file.name = "protected.log"
    mock_file.stat.return_value.st_mtime = 0
    mock_file.stat.return_value.st_size = 1024
    mock_file.unlink.side_effect = PermissionError("Access denied")

    with patch("pathlib.Path") as mock_path_class:
        mock_path = Mock()
        mock_path_class.return_value = mock_path
        mock_path.exists.return_value = True
        mock_path.is_dir.return_value = True
        mock_path.glob.return_value = [mock_file]

        with patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.side_effect = lambda func, *args: func(*args)

            result = await coordinator.async_run_cleanup_now()

    # Should not count as deleted
    assert result["deleted_last_run"] == 0
    assert result["total_files"] == 1


async def test_coordinator_disk_full_error_mocked(
    hass: HomeAssistant, mock_setup_entry_no_dry_run
):
    """Test handling of disk full error."""
    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry_no_dry_run)
    coordinator.dry_run = False

    mock_file = Mock(spec=Path)
    mock_file.name = "test.log"
    mock_file.stat.return_value.st_mtime = 0
    mock_file.stat.return_value.st_size = 1024

    # Simulate disk full error
    error = OSError("No space left on device")
    error.errno = errno.ENOSPC
    mock_file.unlink.side_effect = error

    with patch("pathlib.Path") as mock_path_class:
        mock_path = Mock()
        mock_path_class.return_value = mock_path
        mock_path.exists.return_value = True
        mock_path.is_dir.return_value = True
        mock_path.glob.return_value = [mock_file]

        with patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.side_effect = lambda func, *args: func(*args)

            # Disk full should raise an exception
            with pytest.raises(RuntimeError, match="Disk full"):
                await coordinator.async_run_cleanup_now()
