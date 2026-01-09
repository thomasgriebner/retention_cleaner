"""Test configuration and fixtures for retention_cleaner tests."""

from unittest.mock import Mock, patch

from freezegun import freeze_time
import pytest

# Enable pytest-homeassistant-custom-component fixtures
pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integration for all tests."""
    yield


@pytest.fixture
def mock_setup_entry():
    """Create a mock config entry for testing."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    return MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
            "dry_run": True,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_entry_123",
    )


@pytest.fixture
def mock_setup_entry_no_dry_run():
    """Create a mock config entry with dry run disabled."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    return MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup No Dry Run",
        data={
            "base_path": "/media/test",
            "pattern": "*.log",
            "retention_days": 3,
            "dry_run": False,
            "max_deletes": 50,
            "run_at": "04:00",
        },
        entry_id="test_entry_456",
    )


@pytest.fixture
async def init_integration(hass, mock_setup_entry):
    """Set up the retention_cleaner integration."""
    mock_setup_entry.add_to_hass(hass)

    # Actually setup the integration
    assert await hass.config_entries.async_setup(mock_setup_entry.entry_id)
    await hass.async_block_till_done()

    # Return the config entry which now has runtime_data set
    return hass.config_entries.async_get_entry(mock_setup_entry.entry_id)


@pytest.fixture
def mock_path_glob(tmp_path):
    """Mock Path.glob to return test files."""
    test_files = []
    for i in range(10):
        file = tmp_path / f"test_{i}.jpg"
        file.touch()
        # Set modification time for some files to be old
        if i < 5:
            import os
            import time

            old_time = time.time() - (8 * 24 * 60 * 60)  # 8 days old
            os.utime(file, (old_time, old_time))
        test_files.append(file)

    with patch("pathlib.Path.glob") as mock_glob:
        mock_glob.return_value = test_files
        yield mock_glob, test_files


@pytest.fixture
def mock_file_system_operations():
    """Mock file system operations for testing."""
    with (
        patch("pathlib.Path.exists") as mock_exists,
        patch("pathlib.Path.is_dir") as mock_is_dir,
        patch("pathlib.Path.unlink") as mock_unlink,
        patch("pathlib.Path.stat") as mock_stat,
    ):
        mock_exists.return_value = True
        mock_is_dir.return_value = True

        # Mock stat to return file info
        mock_stat_obj = Mock()
        mock_stat_obj.st_mtime = 1700000000  # Fixed timestamp
        mock_stat_obj.st_size = 1024  # 1KB file
        mock_stat.return_value = mock_stat_obj

        yield {
            "exists": mock_exists,
            "is_dir": mock_is_dir,
            "unlink": mock_unlink,
            "stat": mock_stat,
        }


@pytest.fixture
def mock_coordinator_data():
    """Mock coordinator data for entity tests."""
    return {
        "total_files": 100,
        "older_than_retention": 25,
        "deleted_last_run": 10,
        "deleted_bytes_last_run": 102400,
        "last_scan": "2024-01-01T12:00:00",
        "last_cleanup": "2024-01-01T02:00:00",
        "last_scan_duration_ms": 150.5,
        "last_cleanup_duration_ms": 500.2,
        "path_accessible": True,
    }


@pytest.fixture
def freezer():
    """Freeze time for testing scheduled operations."""
    with freeze_time("2024-01-01 12:00:00") as frozen_time:
        yield frozen_time
