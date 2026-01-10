"""Test to verify mock override strategy works correctly."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest


async def test_mock_override_verification(
    hass: HomeAssistant, init_integration_no_glob_mock
):
    """Verify that our mock override strategy works correctly.

    This test ensures that:
    1. init_integration_no_glob_mock fixture doesn't mock Path.glob
    2. We can successfully mock Path.glob in the test
    3. The exception propagates correctly through the coordinator
    """
    config_entry = init_integration_no_glob_mock
    coordinator = config_entry.runtime_data

    try:
        # Verify we can mock Path.glob and raise an exception
        test_error = ValueError("Test mock override successful")

        with patch(
            "custom_components.retention_cleaner.coordinator.Path.glob",
            side_effect=test_error,
        ):
            # The exception should propagate through the chain:
            # Path.glob -> _cleanup_folder -> RuntimeError -> UpdateFailed
            with pytest.raises(UpdateFailed) as exc_info:
                await coordinator.async_run_cleanup_now()

            # Verify the exception chain worked correctly
            assert "Cleanup failed:" in str(exc_info.value)
            assert "Test mock override successful" in str(exc_info.value)

        # Also test with scan operation
        with patch(
            "custom_components.retention_cleaner.coordinator.Path.glob",
            side_effect=test_error,
        ):
            with pytest.raises(UpdateFailed) as exc_info:
                await coordinator.async_run_scan_now()

            assert "Scan failed:" in str(exc_info.value)
            assert "Test mock override successful" in str(exc_info.value)

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_original_fixture_still_works(hass: HomeAssistant, init_integration):
    """Verify that the original init_integration fixture still works for other tests."""
    config_entry = init_integration
    coordinator = config_entry.runtime_data

    try:
        # The original fixture mocks Path.glob to return []
        # So operations should complete without error
        await coordinator.async_run_scan_now()
        await hass.async_block_till_done()

        # Should have no files since glob returns []
        assert coordinator.data is not None
        assert coordinator.data["total_files"] == 0
        assert coordinator.data["older_than_retention"] == 0

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()
