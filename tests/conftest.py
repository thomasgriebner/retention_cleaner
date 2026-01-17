"""Test configuration and fixtures for retention_cleaner tests."""

from pathlib import Path
import sys

# Ensure custom_components is importable (needed for direct function imports in sync tests)
_repo_root = Path(__file__).parent.parent.absolute()
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import contextlib
from unittest.mock import Mock, patch

from freezegun import freeze_time
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest

# Enable pytest-homeassistant-custom-component fixtures
pytest_plugins = "pytest_homeassistant_custom_component"


def pytest_configure(config):
    """Configure pytest - ensures custom_components is in sys.path early."""
    repo_root = Path(__file__).parent.parent.absolute()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


# Test Helper Functions
async def assert_exception_chain(operation, expected_error_type, expected_message):
    """Helper to verify complete exception chain.

    Args:
        operation: Async callable that should raise exception
        expected_error_type: Expected exception class
        expected_message: Message that should be in exception

    Returns:
        The exception info for further assertions
    """
    with pytest.raises(expected_error_type) as exc_info:
        await operation()

    assert expected_message in str(exc_info.value)
    return exc_info


async def verify_cleanup_exception_handling(coordinator, exception_to_raise):
    """Verify cleanup operation handles exception correctly.

    Tests the complete chain:
    filesystem error -> RuntimeError -> UpdateFailed
    """
    # Mock Path where it's actually used in the coordinator module
    with patch(
        "custom_components.retention_cleaner.coordinator.Path",
    ) as mock_path_class:
        # Create a mock Path instance that raises the exception on glob
        mock_path_instance = Mock()
        mock_path_class.return_value = mock_path_instance
        mock_path_instance.glob.side_effect = exception_to_raise
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_dir.return_value = True

        return await assert_exception_chain(
            coordinator.async_run_cleanup_now, UpdateFailed, "Cleanup failed:"
        )


async def verify_scan_exception_handling(coordinator, exception_to_raise):
    """Verify scan operation handles exception correctly.

    Tests the complete chain:
    filesystem error -> RuntimeError -> UpdateFailed
    """
    # Mock Path where it's actually used in the coordinator module
    with patch(
        "custom_components.retention_cleaner.coordinator.Path",
    ) as mock_path_class:
        # Create a mock Path instance that raises the exception on glob
        mock_path_instance = Mock()
        mock_path_class.return_value = mock_path_instance
        mock_path_instance.glob.side_effect = exception_to_raise
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_dir.return_value = True

        return await assert_exception_chain(
            coordinator.async_run_scan_now, UpdateFailed, "Scan failed:"
        )


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


async def _setup_integration_base(
    hass, entry, mock_glob=True, glob_return_value=None, keep_mocks=False
):
    """Shared integration setup logic.

    Args:
        hass: Home Assistant instance
        entry: Config entry to setup
        mock_glob: Whether to mock Path.glob
        glob_return_value: Value to return from Path.glob mock
        keep_mocks: If True, return active mock context manager
    """
    entry.add_to_hass(hass)

    # Build patch list based on parameters
    patches = [
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
    ]

    if mock_glob:
        if glob_return_value is not None:
            patches.append(patch("pathlib.Path.glob", return_value=glob_return_value))
        else:
            patches.append(patch("pathlib.Path.glob", return_value=[]))

    if keep_mocks:
        # Keep mocks active and return them with the entry
        stack = contextlib.ExitStack()
        mock_objects = {}
        for p in patches:
            mock_obj = stack.enter_context(p)
            # Store references to the mock objects
            if "exists" in str(p):
                mock_objects["exists"] = mock_obj
            elif "is_dir" in str(p):
                mock_objects["is_dir"] = mock_obj
            elif "glob" in str(p):
                mock_objects["glob"] = mock_obj

        # Setup the integration with mocks active
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Store mocks and stack on entry for cleanup
        entry._mock_stack = stack
        entry._mock_objects = mock_objects
    else:
        # Original behavior - mocks only during setup
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            # Setup the integration
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

    # Verify runtime_data was set during setup
    assert hasattr(entry, "runtime_data")
    assert entry.runtime_data is not None

    return entry


@pytest.fixture
async def init_integration(hass, mock_setup_entry):
    """Set up the retention_cleaner integration with default mocks."""
    return await _setup_integration_base(hass, mock_setup_entry, mock_glob=True)


@pytest.fixture
async def init_integration_with_exception(hass, mock_setup_entry, request):
    """Set up integration with configurable exception on Path.glob.

    Usage in test:
        @pytest.mark.parametrize(
            "init_integration_with_exception",
            [{"exception": PermissionError("No access")}],
            indirect=True
        )
        async def test_permission_error(init_integration_with_exception):
            ...
    """
    exception = request.param.get("exception", Exception("Test error"))

    entry = await _setup_integration_base(hass, mock_setup_entry, mock_glob=False)

    # Patch Path.glob at coordinator module level to raise exception
    with patch(
        "custom_components.retention_cleaner.coordinator.Path.glob",
        side_effect=exception,
    ):
        yield entry


@pytest.fixture
def mock_coordinator_data():
    """Mock coordinator data for entity tests."""
    from datetime import UTC, datetime

    return {
        "total_files": 100,
        "older_than_retention": 25,
        "deleted_last_run": 10,
        "deleted_bytes_last_run": 102400,
        "last_scan": datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        "last_cleanup": datetime(2024, 1, 1, 2, 0, 0, tzinfo=UTC),
        "last_scan_duration_ms": 150,  # int milliseconds
        "last_cleanup_duration_ms": 500,  # int milliseconds
        "path_available": True,
    }


@pytest.fixture
def freezer():
    """Freeze time for testing scheduled operations."""
    with freeze_time("2024-01-01 12:00:00") as frozen_time:
        yield frozen_time
