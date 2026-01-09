"""Test fixtures and configuration for retention cleaner tests."""
import pytest
from unittest.mock import Mock, patch

# Import constants without HA dependencies
try:
    from custom_components.retention_cleaner.const import (
        DOMAIN,
        CONF_BASE_PATH,
        CONF_PATTERN,
        CONF_RETENTION_DAYS,
        CONF_DRY_RUN,
        CONF_MAX_DELETES,
        CONF_SCHEDULE_TIME,
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
def mock_hass():
    """Mock Home Assistant instance."""
    hass = Mock()
    hass.config_entries = Mock()
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