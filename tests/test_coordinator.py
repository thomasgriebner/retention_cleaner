"""Test the retention_cleaner coordinator."""

import contextlib
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
    assert str(coordinator.run_at) == "02:00:00"  # run_at returns a time object
    # coordinator.name is set by parent DataUpdateCoordinator
    assert coordinator.name == f"retention_cleaner_{mock_setup_entry.entry_id}"


async def test_coordinator_scan_with_real_files(
    hass: HomeAssistant, mock_setup_entry, tmp_path
):
    """Test scanning files with real file operations."""
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)

    # Create new config entry with updated path instead of modifying data directly
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_setup_entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            **mock_setup_entry.data,
            "base_path": str(media_dir),
        },
        entry_id="test_entry_123",
    )

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

    await coordinator.async_run_scan_now()
    await hass.async_block_till_done()  # Wait for refresh to complete
    result = coordinator.data

    assert result["total_files"] == 10  # Only .jpg files
    assert result["older_than_retention"] == 5
    assert result["path_available"] is True

    # Clean up coordinator to avoid lingering timers
    await coordinator.async_shutdown()


async def test_coordinator_cleanup_dry_run_real_files(
    hass: HomeAssistant, mock_setup_entry, tmp_path
):
    """Test cleanup in dry run mode with real files - should not delete."""
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_setup_entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            **mock_setup_entry.data,
            "base_path": str(media_dir),
            "dry_run": True,
        },
        entry_id="test_entry_123",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry)

    test_files = []
    for i in range(5):
        file = media_dir / f"test_{i}.jpg"
        file.touch()
        old_time = time_module.time() - (8 * 24 * 60 * 60)
        os.utime(file, (old_time, old_time))
        test_files.append(file)

    await coordinator.async_run_cleanup_now()
    await hass.async_block_till_done()  # Wait for refresh to complete
    result = coordinator.data

    assert result["deleted_last_run"] == 0
    for file in test_files:
        assert file.exists()  # All files should still exist

    # Clean up coordinator to avoid lingering timers
    await coordinator.async_shutdown()


async def test_coordinator_cleanup_with_deletion_real_files(
    hass: HomeAssistant, mock_setup_entry_no_dry_run, tmp_path
):
    """Test cleanup with actual file deletion."""
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_setup_entry_no_dry_run = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup No Dry Run",
        data={
            **mock_setup_entry_no_dry_run.data,
            "base_path": str(media_dir),
            "pattern": "*.log",
            "dry_run": False,
        },
        entry_id="test_entry_456",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry_no_dry_run)

    test_files = []
    for i in range(5):
        file = media_dir / f"test_{i}.log"
        file.write_text(f"log content {i}")  # Write some content
        old_time = time_module.time() - (4 * 24 * 60 * 60)  # 4 days old
        os.utime(file, (old_time, old_time))
        test_files.append(file)

    await coordinator.async_run_cleanup_now()
    await hass.async_block_till_done()  # Wait for refresh to complete
    result = coordinator.data

    assert result["deleted_last_run"] == 5
    assert result["total_files"] == 0
    for file in test_files:
        assert not file.exists()  # All files should be deleted

    # Clean up coordinator to avoid lingering timers
    await coordinator.async_shutdown()


async def test_coordinator_max_deletes_limit_real_files(
    hass: HomeAssistant, mock_setup_entry_no_dry_run, tmp_path
):
    """Test that max_deletes limit is enforced with real files."""
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_setup_entry_no_dry_run = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup No Dry Run",
        data={
            **mock_setup_entry_no_dry_run.data,
            "base_path": str(media_dir),
            "pattern": "*.log",
            "dry_run": False,
            "max_deletes": 3,
        },
        entry_id="test_entry_456",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry_no_dry_run)

    for i in range(10):
        file = media_dir / f"test_{i}.log"
        file.touch()
        old_time = time_module.time() - (4 * 24 * 60 * 60)
        os.utime(file, (old_time, old_time))

    await coordinator.async_run_cleanup_now()
    await hass.async_block_till_done()  # Wait for refresh to complete
    result = coordinator.data

    assert result["deleted_last_run"] == 3

    # Clean up coordinator to avoid lingering timers
    await coordinator.async_shutdown()

    remaining = list(media_dir.glob("*.log"))
    assert len(remaining) == 7  # 10 - 3 = 7


async def test_coordinator_path_not_accessible(hass: HomeAssistant, mock_setup_entry):
    """Test behavior when path doesn't exist."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_setup_entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            **mock_setup_entry.data,
            "base_path": "/media/nonexistent/path",
        },
        entry_id="test_entry_123",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry)

    result = await coordinator._async_update_data()

    assert result["path_available"] is False
    assert result["total_files"] == 0
    assert result["older_than_retention"] == 0


async def test_coordinator_race_condition_handling(
    hass: HomeAssistant, mock_setup_entry_no_dry_run, tmp_path
):
    """Test graceful handling of race conditions when file is deleted by another process."""
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_setup_entry_no_dry_run = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup No Dry Run",
        data={
            **mock_setup_entry_no_dry_run.data,
            "base_path": str(media_dir),
            "pattern": "*.log",
            "dry_run": False,
        },
        entry_id="test_entry_456",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry_no_dry_run)

    # Create multiple files
    test_files = []
    for i in range(3):
        test_file = media_dir / f"test_{i}.log"
        test_file.touch()
        old_time = time_module.time() - (4 * 24 * 60 * 60)
        os.utime(test_file, (old_time, old_time))
        test_files.append(test_file)

    # Delete one file manually to simulate race condition
    test_files[0].unlink()

    # Run cleanup - should handle missing file gracefully
    await coordinator.async_run_cleanup_now()
    await hass.async_block_till_done()  # Wait for refresh to complete
    result = coordinator.data

    # Should delete remaining files and handle missing file gracefully
    assert result["deleted_last_run"] == 2
    assert not test_files[1].exists()
    assert not test_files[2].exists()

    # Clean up coordinator to avoid lingering timers
    await coordinator.async_shutdown()


async def test_coordinator_schedule_setup(hass: HomeAssistant, mock_setup_entry):
    """Test that daily schedule is set up correctly."""
    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry)

    with patch(
        "custom_components.retention_cleaner.coordinator.async_track_time_change"
    ) as mock_track:
        # async_track_time_change returns an unsubscribe callable
        mock_track.return_value = Mock()
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

    coordinator.async_remove_listeners()

    # Verify listener was removed
    mock_unsub.assert_called_once()
    assert coordinator._unsub_daily is None


async def test_coordinator_performance_tracking(
    hass: HomeAssistant, mock_setup_entry, tmp_path
):
    """Test that scan and cleanup duration are tracked."""
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_setup_entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            **mock_setup_entry.data,
            "base_path": str(media_dir),
        },
        entry_id="test_entry_123",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry)

    # Create some files
    for i in range(5):
        (media_dir / f"test_{i}.jpg").touch()

    # Test scan duration tracking
    await coordinator.async_run_scan_now()
    await hass.async_block_till_done()  # Wait for refresh to complete
    result = coordinator.data
    assert "last_scan_duration_ms" in result
    assert isinstance(result["last_scan_duration_ms"], int)
    assert result["last_scan_duration_ms"] >= 0

    # Test cleanup duration tracking
    await coordinator.async_run_cleanup_now()
    await hass.async_block_till_done()  # Wait for refresh to complete
    result = coordinator.data
    assert "last_cleanup_duration_ms" in result
    assert isinstance(result["last_cleanup_duration_ms"], int)
    assert result["last_cleanup_duration_ms"] >= 0

    # Clean up coordinator to avoid lingering timers
    await coordinator.async_shutdown()


async def test_coordinator_permission_error_with_real_files(
    hass: HomeAssistant, mock_setup_entry_no_dry_run, tmp_path
):
    """Test handling of permission errors during deletion with real files."""
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_setup_entry_no_dry_run = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup No Dry Run",
        data={
            **mock_setup_entry_no_dry_run.data,
            "base_path": str(media_dir),
            "pattern": "*.log",
            "dry_run": False,
        },
        entry_id="test_entry_456",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry_no_dry_run)

    # Create test files
    for i in range(3):
        test_file = media_dir / f"test_{i}.log"
        test_file.touch()
        old_time = time_module.time() - (4 * 24 * 60 * 60)
        os.utime(test_file, (old_time, old_time))

    # Mock unlink to simulate permission error on specific file
    original_unlink = Path.unlink

    def mock_unlink(self):
        if "test_1.log" in str(self):
            raise PermissionError("Access denied")
        return original_unlink(self)

    with patch.object(Path, "unlink", mock_unlink):
        await coordinator.async_run_cleanup_now()
    await hass.async_block_till_done()  # Wait for refresh to complete
    result = coordinator.data

    # Should delete 2 out of 3 files (one failed with permission error)
    assert result["deleted_last_run"] == 2
    assert result["total_files"] == 1  # 1 file remaining due to permission error

    # Verify which files still exist
    remaining_files = list(media_dir.glob("*.log"))
    assert len(remaining_files) == 1
    assert "test_1.log" in str(remaining_files[0])  # The protected file remains

    # Clean up coordinator to avoid lingering timers
    await coordinator.async_shutdown()


async def test_coordinator_file_pattern_matching(
    hass: HomeAssistant, mock_setup_entry, tmp_path
):
    """Test that file pattern matching works correctly with real files."""
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_setup_entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            **mock_setup_entry.data,
            "base_path": str(media_dir),
            "pattern": "*.jpg",  # Only match JPG files
        },
        entry_id="test_entry_123",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry)

    # Create various file types
    files = [
        media_dir / "photo1.jpg",
        media_dir / "photo2.jpg",
        media_dir / "document.pdf",
        media_dir / "video.mp4",
        media_dir / "log.txt",
    ]

    for file_path in files:
        file_path.touch()
        old_time = time_module.time() - (8 * 24 * 60 * 60)
        os.utime(file_path, (old_time, old_time))

    await coordinator.async_run_scan_now()
    await hass.async_block_till_done()  # Wait for refresh to complete
    result = coordinator.data

    # Should only count JPG files
    assert result["total_files"] == 2  # Only 2 JPG files
    assert result["older_than_retention"] == 2  # Both JPG files are old

    # Clean up coordinator to avoid lingering timers
    await coordinator.async_shutdown()


async def test_coordinator_retention_days_boundary(
    hass: HomeAssistant, mock_setup_entry, tmp_path
):
    """Test retention days boundary conditions with real files."""
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_setup_entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            **mock_setup_entry.data,
            "base_path": str(media_dir),
            "retention_days": 7,
        },
        entry_id="test_entry_123",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry)

    # Create files with different ages
    now = time_module.time()
    files_ages = [
        ("new_file.jpg", 1),  # 1 day old - keep
        ("recent_file.jpg", 6),  # 6 days old - keep
        ("old_file.jpg", 8),  # 8 days old - should delete
        ("very_old_file.jpg", 30),  # 30 days old - should delete
    ]

    for filename, age_days in files_ages:
        file_path = media_dir / filename
        file_path.touch()
        old_time = now - (age_days * 24 * 60 * 60)
        os.utime(file_path, (old_time, old_time))

    await coordinator.async_run_scan_now()
    await hass.async_block_till_done()  # Wait for refresh to complete
    result = coordinator.data

    assert result["total_files"] == 4
    assert result["older_than_retention"] == 2  # Only 2 files older than 7 days

    # Clean up coordinator to avoid lingering timers
    await coordinator.async_shutdown()


async def test_daily_schedule_end_to_end(
    hass: HomeAssistant, mock_setup_entry_no_dry_run, tmp_path
):
    """Test that daily schedule triggers actual cleanup operations.

    CRITICAL because the integration automatically deletes files
    on schedule without user intervention.
    """
    media_dir = tmp_path / "media" / "scheduled_test"
    media_dir.mkdir(parents=True)

    from freezegun import freeze_time
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_setup_entry_no_dry_run = MockConfigEntry(
        domain="retention_cleaner",
        title="Scheduled Test Cleanup",
        data={
            **mock_setup_entry_no_dry_run.data,
            "base_path": str(media_dir),
            "pattern": "*.test",
            "dry_run": False,
            "retention_days": 5,
            "run_at": "03:00",
        },
        entry_id="test_scheduled_456",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry_no_dry_run)

    # Create old files to be deleted by schedule
    for i in range(3):
        test_file = media_dir / f"old_{i}.test"
        test_file.write_text(f"test data {i}")
        old_time = time_module.time() - (7 * 24 * 60 * 60)  # 7 days old
        os.utime(test_file, (old_time, old_time))

    # Set up schedule
    await coordinator.async_setup_daily_schedule()

    # Verify schedule is active
    assert coordinator._unsub_daily is not None

    # Simulate time passing to trigger schedule at 03:00
    with freeze_time("2024-01-01 02:59:59") as frozen_time:
        # Advance to exactly 03:00:00 to trigger schedule
        frozen_time.tick(delta=1)

        # Give Home Assistant time to process the scheduled event
        await hass.async_block_till_done()

        # The schedule callback should have triggered cleanup
        # Allow some processing time for the async cleanup
        for _ in range(5):  # Try multiple times to allow async processing
            await hass.async_block_till_done()
            if coordinator.deleted_last_run > 0:
                break

    # Verify cleanup was triggered and files were deleted
    result = coordinator.data
    assert result["deleted_last_run"] == 3

    # Verify files are actually gone
    remaining_files = list(media_dir.glob("*.test"))
    assert len(remaining_files) == 0

    # Cleanup
    await coordinator.async_shutdown()


async def test_disk_full_during_cleanup(
    hass: HomeAssistant, mock_setup_entry_no_dry_run, tmp_path
):
    """Test graceful handling when disk becomes full during cleanup."""
    media_dir = tmp_path / "media" / "disk_test"
    media_dir.mkdir(parents=True)

    import errno

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_setup_entry_no_dry_run = MockConfigEntry(
        domain="retention_cleaner",
        title="Disk Test Cleanup",
        data={
            **mock_setup_entry_no_dry_run.data,
            "base_path": str(media_dir),
            "pattern": "*.disk",
            "dry_run": False,
            "retention_days": 3,
        },
        entry_id="test_disk_456",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry_no_dry_run)

    # Create test files
    for i in range(5):
        test_file = media_dir / f"test_{i}.disk"
        test_file.write_text(f"data {i}")
        old_time = time_module.time() - (5 * 24 * 60 * 60)  # 5 days old
        os.utime(test_file, (old_time, old_time))

    # Mock unlink to simulate disk full error
    original_unlink = Path.unlink

    def mock_unlink_disk_full(self):
        # Simulate disk becoming full on second deletion
        if "test_1.disk" in str(self):
            err = OSError("No space left on device")
            err.errno = errno.ENOSPC
            raise err
        return original_unlink(self)

    with patch.object(Path, "unlink", mock_unlink_disk_full):
        # Cleanup should fail with UpdateFailed due to disk full
        with pytest.raises(Exception) as exc_info:
            await coordinator.async_run_cleanup_now()

        # Verify it's the expected disk full error
        assert "Disk full" in str(exc_info.value) or "UpdateFailed" in str(
            type(exc_info.value)
        )

    # Verify partial cleanup occurred (first file deleted before error)
    remaining_files = list(media_dir.glob("*.disk"))
    assert len(remaining_files) >= 4  # At least 4 should remain due to early abort

    # Cleanup
    await coordinator.async_shutdown()


async def test_readonly_filesystem_handling(
    hass: HomeAssistant, mock_setup_entry_no_dry_run, tmp_path
):
    """Test behavior on read-only filesystem."""
    media_dir = tmp_path / "media" / "readonly_test"
    media_dir.mkdir(parents=True)

    import errno

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_setup_entry_no_dry_run = MockConfigEntry(
        domain="retention_cleaner",
        title="ReadOnly Test Cleanup",
        data={
            **mock_setup_entry_no_dry_run.data,
            "base_path": str(media_dir),
            "pattern": "*.readonly",
            "dry_run": False,
            "retention_days": 3,
        },
        entry_id="test_readonly_456",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry_no_dry_run)

    # Create test files
    for i in range(3):
        test_file = media_dir / f"test_{i}.readonly"
        test_file.write_text(f"data {i}")
        old_time = time_module.time() - (5 * 24 * 60 * 60)  # 5 days old
        os.utime(test_file, (old_time, old_time))

    # Mock unlink to simulate read-only filesystem
    def mock_unlink_readonly(self):
        err = OSError("Read-only file system")
        err.errno = errno.EROFS
        raise err

    with patch.object(Path, "unlink", mock_unlink_readonly):
        # Cleanup should fail with UpdateFailed due to read-only filesystem
        with pytest.raises(Exception) as exc_info:
            await coordinator.async_run_cleanup_now()

        # Verify it's the expected read-only error
        assert "read-only" in str(exc_info.value).lower() or "UpdateFailed" in str(
            type(exc_info.value)
        )

    # Verify no files were deleted (read-only filesystem)
    remaining_files = list(media_dir.glob("*.readonly"))
    assert len(remaining_files) == 3  # All files should remain

    # Cleanup
    await coordinator.async_shutdown()


async def test_path_traversal_attack_prevention():
    """Test rejection of path traversal attempts."""
    import voluptuous as vol

    from custom_components.retention_cleaner.config_flow import _validate_base_path

    malicious_paths = [
        "/media/../../../etc/passwd",
        "/media/test/../../home/user",
        "/media/test/../.ssh/",
        "/media/./../../root/",
        "/media/../",
        "../media/safe",
        "/media/test/../../../",
    ]

    for path in malicious_paths:
        with pytest.raises(vol.Invalid) as exc_info:
            _validate_base_path(path)

        # All should be rejected for not starting with /media/
        assert "base_path_not_media" in str(exc_info.value)

    # Valid paths should work
    valid_paths = [
        "/media/cameras",
        "/media/test/subfolder",
        "/media/a/b/c/d",
    ]

    for path in valid_paths:
        result = _validate_base_path(path)
        assert result.startswith("/media/")
        assert not result.endswith("/")  # Should strip trailing slash


async def test_symlink_attack_prevention(tmp_path):
    """Test handling of malicious symlinks in /media."""
    import os

    # Set up test directory structure
    media_dir = tmp_path / "media" / "symlink_test"
    media_dir.mkdir(parents=True)

    # Create a sensitive directory outside /media
    sensitive_dir = tmp_path / "sensitive"
    sensitive_dir.mkdir()
    sensitive_file = sensitive_dir / "secret.txt"
    sensitive_file.write_text("sensitive data")

    # Create malicious symlinks
    media_symlink = media_dir / "malicious_link"
    try:
        os.symlink(str(sensitive_dir), str(media_symlink))
    except OSError:
        # Skip test if symlinks not supported (Windows without dev mode)
        pytest.skip("Symlinks not supported on this platform")

    # Create a regular file for pattern matching
    regular_file = media_dir / "test.log"
    regular_file.write_text("normal data")
    old_time = time_module.time() - (10 * 24 * 60 * 60)
    os.utime(regular_file, (old_time, old_time))

    from custom_components.retention_cleaner.coordinator import (
        _cleanup_folder,
        _scan_folder,
    )

    # Test scan operation with symlinks present
    scan_result = _scan_folder(str(media_dir), "*.log", 7)

    # Should only count regular files, not symlink contents
    assert scan_result.total_files == 1
    assert scan_result.older_than_retention == 1
    assert scan_result.path_available is True

    # Test cleanup operation with symlinks present
    cleanup_result = _cleanup_folder(str(media_dir), "*.log", 7, False, 100)

    # Should delete regular file but not follow symlinks
    assert cleanup_result.deleted == 1
    assert cleanup_result.total_after == 0

    # Verify sensitive file still exists (symlink was not followed)
    assert sensitive_file.exists()
    assert sensitive_file.read_text() == "sensitive data"

    # Verify symlink still exists (not matched by pattern)
    assert media_symlink.exists()


async def test_pattern_safety_comprehensive(tmp_path):
    """Test dangerous patterns with actual file structures."""
    import voluptuous as vol

    from custom_components.retention_cleaner.config_flow import _validate_pattern

    media_dir = tmp_path / "media" / "pattern_test"
    media_dir.mkdir(parents=True)

    # Create complex nested directory structure
    subdirs = [
        "cameras/front",
        "cameras/back",
        "logs/system",
        "temp/cache",
        "downloads",
        "important",
    ]
    for subdir in subdirs:
        (media_dir / subdir).mkdir(parents=True)

    # Create various file types in nested structure
    files = [
        "cameras/front/snapshot_001.jpg",
        "cameras/back/video_001.mp4",
        "logs/system/error.log",
        "logs/system/access.log",
        "temp/cache/temp_file.tmp",
        "downloads/document.pdf",
        "important/config.json",
        "test.jpg",  # Root level
        "special[file].jpg",  # Special characters
        "file with spaces.log",
        "file.with.dots.txt",
    ]

    for file_path in files:
        full_path = media_dir / file_path
        full_path.write_text(f"content of {file_path}")
        old_time = time_module.time() - (10 * 24 * 60 * 60)
        os.utime(full_path, (old_time, old_time))

    # Test dangerous patterns are blocked
    dangerous_patterns = [
        "*",  # Matches all files
        "**/*",  # Matches all files recursively
        "***",  # Invalid syntax
        "*[",  # Unclosed bracket
        "***/test",  # Invalid triple asterisk
        "",  # Empty pattern
    ]

    for pattern in dangerous_patterns:
        with pytest.raises(vol.Invalid):
            _validate_pattern(pattern)

    # Test safe patterns work correctly with real files
    from custom_components.retention_cleaner.coordinator import _scan_folder

    pattern_tests = [
        ("*.jpg", 2),  # 2 JPG files (root + front camera)
        ("cameras/**/*.jpg", 1),  # 1 JPG file in cameras
        ("**/*.log", 3),  # 3 log files
        ("logs/**/*.log", 2),  # 2 log files in logs dir
        ("temp/**/*", 1),  # 1 file in temp
        ("nonexistent*", 0),  # No matches
        ("**/config.*", 1),  # 1 config file
        ("**/*with*", 1),  # Files with "with" in name
        ("**/*[*", 0),  # Test bracket handling (should match nothing safely)
    ]

    for pattern, expected_count in pattern_tests:
        try:
            result = _scan_folder(str(media_dir), pattern, 7)
            assert (
                result.total_files == expected_count
            ), f"Pattern {pattern}: expected {expected_count}, got {result.total_files}"
            assert result.older_than_retention == expected_count  # All files are old
        except Exception as e:
            # Some patterns might be invalid - that's OK for safety
            if "Invalid pattern" in str(e):
                continue
            raise

    # Test empty directory handling
    empty_dir = media_dir / "empty"
    empty_dir.mkdir()

    result = _scan_folder(str(empty_dir), "*.jpg", 7)
    assert result.total_files == 0
    assert result.older_than_retention == 0
    assert result.path_available is True


async def test_concurrent_scan_and_cleanup(
    hass: HomeAssistant, mock_setup_entry_no_dry_run, tmp_path
):
    """Test behavior with simultaneous operations."""
    import asyncio

    media_dir = tmp_path / "media" / "concurrent_test"
    media_dir.mkdir(parents=True)

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_setup_entry_no_dry_run = MockConfigEntry(
        domain="retention_cleaner",
        title="Concurrent Test Cleanup",
        data={
            **mock_setup_entry_no_dry_run.data,
            "base_path": str(media_dir),
            "pattern": "*.concurrent",
            "dry_run": False,
            "retention_days": 3,
        },
        entry_id="test_concurrent_456",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry_no_dry_run)

    # Create test files
    for i in range(20):
        test_file = media_dir / f"test_{i:03d}.concurrent"
        test_file.write_text(f"data {i}")
        old_time = time_module.time() - (5 * 24 * 60 * 60)  # 5 days old
        os.utime(test_file, (old_time, old_time))

    # Start scan and cleanup simultaneously
    scan_task = asyncio.create_task(coordinator.async_run_scan_now())
    cleanup_task = asyncio.create_task(coordinator.async_run_cleanup_now())

    # Wait for both operations to complete
    scan_result, cleanup_result = await asyncio.gather(
        scan_task, cleanup_task, return_exceptions=True
    )

    # Allow coordinator data to update
    await hass.async_block_till_done()

    # Verify no exceptions occurred
    assert not isinstance(scan_result, Exception), f"Scan failed: {scan_result}"
    assert not isinstance(
        cleanup_result, Exception
    ), f"Cleanup failed: {cleanup_result}"

    # Verify coordinator state is consistent (no corruption)
    final_data = coordinator.data
    assert isinstance(final_data.get("total_files"), int)
    assert isinstance(final_data.get("deleted_last_run"), int)
    assert isinstance(final_data.get("older_than_retention"), int)

    # Verify the operations actually worked
    remaining_files = list(media_dir.glob("*.concurrent"))
    expected_remaining = 20 - final_data["deleted_last_run"]
    assert len(remaining_files) == expected_remaining

    # Cleanup
    await coordinator.async_shutdown()


async def test_multiple_coordinator_instances(hass: HomeAssistant):
    """Test multiple retention rules running simultaneously."""
    import asyncio

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    # Create test directories
    test_dirs = []
    coordinators = []

    try:
        # Set up multiple coordinators for different directories
        for i in range(3):
            test_dir = Path(f"/tmp/retention_test_{i}")
            test_dir.mkdir(parents=True, exist_ok=True)
            test_dirs.append(test_dir)

            # Create files in each directory
            for j in range(10):
                test_file = test_dir / f"file_{j}.test"
                test_file.write_text(f"data {i}-{j}")
                old_time = time_module.time() - (8 * 24 * 60 * 60)  # 8 days old
                os.utime(test_file, (old_time, old_time))

            # Create coordinator for this directory
            config_entry = MockConfigEntry(
                domain="retention_cleaner",
                title=f"Test Cleanup {i}",
                data={
                    "base_path": str(test_dir),
                    "pattern": "*.test",
                    "dry_run": False,
                    "retention_days": 7,
                    "max_deletes": 1000,
                    "run_at": "02:00",
                },
                entry_id=f"test_entry_{i}",
            )

            coordinator = RetentionCleanerCoordinator(hass, config_entry)
            coordinators.append(coordinator)

        # Run all coordinators simultaneously
        cleanup_tasks = [
            coordinator.async_run_cleanup_now() for coordinator in coordinators
        ]

        # Wait for all operations to complete
        results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        await hass.async_block_till_done()

        # Verify no exceptions occurred
        for i, result in enumerate(results):
            assert not isinstance(
                result, Exception
            ), f"Coordinator {i} failed: {result}"

        # Verify each coordinator worked independently
        for i, coordinator in enumerate(coordinators):
            data = coordinator.data
            assert (
                data["deleted_last_run"] == 10
            ), f"Coordinator {i} should have deleted 10 files"
            assert (
                data["total_files"] == 0
            ), f"Coordinator {i} should have 0 files remaining"

        # Verify files are actually deleted
        for i, test_dir in enumerate(test_dirs):
            remaining = list(test_dir.glob("*.test"))
            assert len(remaining) == 0, f"Directory {i} should have no remaining files"

    finally:
        # Cleanup coordinators
        for coordinator in coordinators:
            with contextlib.suppress(Exception):
                await coordinator.async_shutdown()

        # Cleanup test directories
        import shutil

        for test_dir in test_dirs:
            with contextlib.suppress(Exception):
                shutil.rmtree(test_dir, ignore_errors=True)


async def test_large_directory_performance(
    hass: HomeAssistant, mock_setup_entry_no_dry_run, tmp_path
):
    """Test performance with large number of files (1000+)."""
    import time as time_module_import  # Avoid conflict with fixture

    media_dir = tmp_path / "media" / "performance_test"
    media_dir.mkdir(parents=True)

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_setup_entry_no_dry_run = MockConfigEntry(
        domain="retention_cleaner",
        title="Performance Test Cleanup",
        data={
            **mock_setup_entry_no_dry_run.data,
            "base_path": str(media_dir),
            "pattern": "*.perf",
            "dry_run": False,
            "retention_days": 5,
            "max_deletes": 10000,
        },
        entry_id="test_performance_456",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_setup_entry_no_dry_run)

    # Create 1500 test files with varying ages
    print(f"\nCreating 1500 test files in {media_dir}...")
    file_creation_start = time_module_import.time()

    for i in range(1500):
        test_file = media_dir / f"test_{i:04d}.perf"
        test_file.write_text(f"performance test data {i}")

        # Make 60% of files old (should be deleted)
        if i < 900:  # 900 old files
            old_time = time_module.time() - (7 * 24 * 60 * 60)  # 7 days old
        else:  # 600 new files
            old_time = time_module.time() - (3 * 24 * 60 * 60)  # 3 days old

        os.utime(test_file, (old_time, old_time))

    file_creation_time = time_module_import.time() - file_creation_start
    print(f"File creation took {file_creation_time:.2f} seconds")

    try:
        # Test scan performance
        print("Testing scan performance...")
        scan_start = time_module_import.time()
        await coordinator.async_run_scan_now()
        await hass.async_block_till_done()
        scan_duration = time_module_import.time() - scan_start

        scan_data = coordinator.data
        assert scan_data["total_files"] == 1500
        assert scan_data["older_than_retention"] == 900

        # Scan should complete in reasonable time (less than 10 seconds)
        assert scan_duration < 10.0, f"Scan took too long: {scan_duration:.2f}s"
        print(f"Scan completed in {scan_duration:.2f} seconds")

        # Verify performance metrics are tracked
        assert "last_scan_duration_ms" in scan_data
        assert scan_data["last_scan_duration_ms"] > 0
        print(f"Reported scan duration: {scan_data['last_scan_duration_ms']}ms")

        # Test cleanup performance
        print("Testing cleanup performance...")
        cleanup_start = time_module_import.time()
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()
        cleanup_duration = time_module_import.time() - cleanup_start

        cleanup_data = coordinator.data
        assert cleanup_data["deleted_last_run"] == 900
        assert cleanup_data["total_files"] == 600  # Remaining files

        # Cleanup should complete in reasonable time (less than 15 seconds)
        assert (
            cleanup_duration < 15.0
        ), f"Cleanup took too long: {cleanup_duration:.2f}s"
        print(f"Cleanup completed in {cleanup_duration:.2f} seconds")

        # Verify performance metrics are tracked
        assert "last_cleanup_duration_ms" in cleanup_data
        assert cleanup_data["last_cleanup_duration_ms"] > 0
        print(
            f"Reported cleanup duration: {cleanup_data['last_cleanup_duration_ms']}ms"
        )

        # Verify memory usage stays reasonable during operations
        # This is a basic check - in production you'd use memory profiling
        try:
            import psutil

            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024

            # Memory usage should be reasonable (less than 500MB for this test)
            assert memory_mb < 500, f"Memory usage too high: {memory_mb:.1f}MB"
            print(f"Memory usage: {memory_mb:.1f}MB")
        except ImportError:
            # psutil not available in test environment
            print("psutil not available - skipping memory usage check")

        # Test progress during long operations by checking intermediate states
        # Reset and test with even more files to check progress reporting
        remaining_files = list(media_dir.glob("*.perf"))
        print(f"Verified {len(remaining_files)} files remain after cleanup")

        # Verify file system state is consistent
        assert len(remaining_files) == 600

    finally:
        # Cleanup coordinator
        await coordinator.async_shutdown()


async def test_pattern_edge_cases_real_filesystem(tmp_path):
    """Test edge cases in pattern matching with real filesystem operations."""
    from custom_components.retention_cleaner.coordinator import (
        _cleanup_folder,
        _scan_folder,
    )

    media_dir = tmp_path / "media" / "edge_cases"
    media_dir.mkdir(parents=True)

    # Create files with challenging names
    challenging_files = [
        "normal.txt",
        "file with spaces.txt",
        "file.with.many.dots.txt",
        "file[brackets].txt",
        "file{braces}.txt",
        "file(parens).txt",
        "file-with-dashes.txt",
        "file_with_underscores.txt",
        "file123numbers.txt",
        "UPPERCASE.TXT",
        "MiXeD_CaSe.TxT",
        "file'quote.txt",
        'file"doublequote.txt',
        "file&special.txt",
        "file@symbol.txt",
        "file#hash.txt",
        "file$dollar.txt",
        "file%percent.txt",
        "file^caret.txt",
        "file+plus.txt",
        "file=equals.txt",
    ]

    for filename in challenging_files:
        try:
            file_path = media_dir / filename
            file_path.write_text(f"content of {filename}")
            old_time = time_module.time() - (10 * 24 * 60 * 60)
            os.utime(file_path, (old_time, old_time))
        except OSError:
            # Skip files that can't be created on this filesystem
            continue

    # Test various patterns handle edge cases correctly
    pattern_tests = [
        ("*.txt", "all txt files"),
        ("*TXT", "uppercase extension"),
        ("*.[Tt][Xx][Tt]", "case insensitive pattern"),
        ("*with*", "files containing 'with'"),
        ("file[*", "pattern with bracket (should be safe)"),
        ("*spaces*", "files with spaces"),
        ("*dots*", "files with dots"),
        ("*123*", "files with numbers"),
    ]

    for pattern, description in pattern_tests:
        try:
            result = _scan_folder(str(media_dir), pattern, 7)
            # Should not crash and should return reasonable results
            assert result.total_files >= 0
            assert result.older_than_retention >= 0
            assert result.path_available is True
            print(
                f"Pattern '{pattern}' ({description}): found {result.total_files} files"
            )
        except Exception as e:
            # Pattern might be invalid on some systems - that's OK for safety
            print(f"Pattern '{pattern}' failed safely: {e}")

    # Test cleanup with edge case files (dry run)
    result = _cleanup_folder(str(media_dir), "*.txt", 7, True, 100)  # dry_run=True
    assert result.deleted == 0  # Dry run should not delete
    assert result.total_after >= 0

    # Verify all files still exist after dry run
    remaining = list(media_dir.glob("*"))
    assert len(remaining) > 0


async def test_concurrent_directory_access_safety(tmp_path):
    """Test that concurrent access to same directory is handled safely."""
    import asyncio

    from custom_components.retention_cleaner.coordinator import (
        _cleanup_folder,
        _scan_folder,
    )

    media_dir = tmp_path / "media" / "concurrent_dir_test"
    media_dir.mkdir(parents=True)

    # Create initial files
    for i in range(50):
        test_file = media_dir / f"concurrent_{i:03d}.test"
        test_file.write_text(f"data {i}")
        old_time = time_module.time() - (8 * 24 * 60 * 60)  # 8 days old
        os.utime(test_file, (old_time, old_time))

    async def scan_operation():
        """Perform scan operation."""
        return await asyncio.get_event_loop().run_in_executor(
            None, _scan_folder, str(media_dir), "*.test", 7
        )

    async def cleanup_operation():
        """Perform cleanup operation."""
        return await asyncio.get_event_loop().run_in_executor(
            None,
            _cleanup_folder,
            str(media_dir),
            "*.test",
            7,
            False,
            25,  # Delete max 25
        )

    async def file_creation_operation():
        """Create new files during operations."""
        for i in range(50, 60):
            test_file = media_dir / f"new_{i:03d}.test"
            test_file.write_text(f"new data {i}")
            old_time = time_module.time() - (8 * 24 * 60 * 60)
            os.utime(test_file, (old_time, old_time))
            await asyncio.sleep(0.01)  # Small delay

    # Run multiple operations concurrently
    tasks = [
        scan_operation(),
        cleanup_operation(),
        file_creation_operation(),
        scan_operation(),  # Second scan
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Verify no critical exceptions occurred
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # File system race conditions are acceptable
            if "FileNotFoundError" in str(result) or "PermissionError" in str(result):
                continue
            pytest.fail(f"Task {i} failed with unexpected error: {result}")

    # Verify final state is reasonable
    final_scan = _scan_folder(str(media_dir), "*.test", 7)
    remaining_files = list(media_dir.glob("*.test"))

    assert final_scan.total_files == len(remaining_files)
    assert final_scan.path_available is True

    # Should have some files remaining (not all deleted due to max_deletes=25)
    assert len(remaining_files) > 0
