"""Test the retention_cleaner coordinator."""

import os
from pathlib import Path
import time as time_module
from unittest.mock import Mock, patch

from homeassistant.core import HomeAssistant

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
