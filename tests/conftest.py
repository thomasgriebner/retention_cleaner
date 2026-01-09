"""Test fixtures and configuration for retention cleaner tests."""

from unittest.mock import Mock, patch

import pytest

# Import constants without HA dependencies
try:
    from custom_components.retention_cleaner.const import (
        CONF_BASE_PATH,
        CONF_DRY_RUN,
        CONF_MAX_DELETES,
        CONF_PATTERN,
        CONF_RETENTION_DAYS,
        CONF_SCHEDULE_TIME,
        DOMAIN,
    )
except ImportError:
    # Fallback constants for testing
    DOMAIN = "retention_cleaner"
    CONF_BASE_PATH = "base_path"
    CONF_PATTERN = "pattern"
    CONF_RETENTION_DAYS = "retention_days"
    CONF_DRY_RUN = "dry_run"
    CONF_MAX_DELETES = "max_deletes"
    CONF_SCHEDULE_TIME = "schedule_time"


@pytest.fixture
def mock_config_entry() -> dict:
    """Mock config entry data for testing."""
    return {
        CONF_BASE_PATH: "/media/test",
        CONF_PATTERN: "*.jpg",
        CONF_RETENTION_DAYS: 7,
        CONF_DRY_RUN: True,
        CONF_MAX_DELETES: 100,
        CONF_SCHEDULE_TIME: "02:00",
    }


@pytest.fixture
def mock_config_entry_obj():
    """Mock ConfigEntry object for integration tests."""
    entry = Mock()
    entry.entry_id = "test_entry_123"
    entry.title = "Test Retention Cleaner"
    entry.data = {
        CONF_BASE_PATH: "/media/test",
        CONF_PATTERN: "*.jpg",
        CONF_RETENTION_DAYS: 7,
        CONF_DRY_RUN: True,
        CONF_MAX_DELETES: 100,
        CONF_SCHEDULE_TIME: "02:00",
    }
    return entry


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    from unittest.mock import AsyncMock

    hass = Mock()
    hass.config_entries = Mock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.data = {}
    hass.async_create_task = Mock()
    hass.async_add_executor_job = Mock()
    return hass


@pytest.fixture
def mock_file_system():
    """Mock file system operations."""
    with patch("pathlib.Path") as mock_path:
        # Setup mock path behavior
        mock_instance = Mock()
        mock_path.return_value = mock_instance
        yield mock_path, mock_instance
