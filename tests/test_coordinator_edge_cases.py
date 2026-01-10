"""Edge case tests for retention cleaner coordinator.

Tests for:
- Nested exceptions
- Timeout scenarios
- Thread safety with parallel operations
- Resource cleanup under error conditions
"""

import asyncio
from unittest.mock import Mock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest

from tests.conftest import assert_exception_chain


async def test_nested_exception_handling(
    hass: HomeAssistant, init_integration_no_glob_mock
):
    """Test handling of nested exceptions during cleanup.

    Verifies that when an exception occurs within exception handling,
    the coordinator still properly propagates errors.
    """
    config_entry = init_integration_no_glob_mock
    coordinator = config_entry.runtime_data

    try:
        # Create a nested exception scenario
        def raise_nested_error(*args, **kwargs):
            try:
                raise ValueError("Inner exception")
            except ValueError as e:
                raise RuntimeError("Outer exception while handling inner") from e

        with patch(
            "custom_components.retention_cleaner.coordinator.Path.glob",
            side_effect=raise_nested_error,
        ):
            exc_info = await assert_exception_chain(
                coordinator.async_run_cleanup_now, UpdateFailed, "Cleanup failed:"
            )

            # Verify the outer exception is captured
            assert "Outer exception" in str(exc_info.value)

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_operation_timeout_handling(
    hass: HomeAssistant, init_integration_no_glob_mock
):
    """Test handling of operations that timeout.

    Simulates a long-running filesystem operation that could timeout.
    """
    config_entry = init_integration_no_glob_mock
    coordinator = config_entry.runtime_data

    try:
        # Simulate a very slow glob operation
        async def slow_glob(*args, **kwargs):
            await asyncio.sleep(10)  # Longer than any reasonable timeout
            return []

        with patch(
            "custom_components.retention_cleaner.coordinator.Path",
        ) as mock_path:
            # Create a mock Path instance
            mock_path_instance = Mock()
            mock_path.return_value = mock_path_instance
            mock_path_instance.glob = Mock(side_effect=slow_glob)
            mock_path_instance.exists.return_value = True
            mock_path_instance.is_dir.return_value = True

            # Use a timeout to prevent hanging test
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(coordinator.async_run_scan_now(), timeout=0.5)

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_parallel_operations_thread_safety(
    hass: HomeAssistant, init_integration_no_glob_mock
):
    """Test thread safety with parallel scan and cleanup operations.

    Verifies that concurrent operations don't interfere with each other.
    """
    config_entry = init_integration_no_glob_mock
    coordinator = config_entry.runtime_data

    try:
        call_count = {"scan": 0, "cleanup": 0}

        def track_scan_calls(*args, **kwargs):
            call_count["scan"] += 1
            if call_count["scan"] > 2:
                # After a few calls, raise an error to test error handling
                raise ValueError(f"Scan error {call_count['scan']}")
            return []

        def track_cleanup_calls(*args, **kwargs):
            call_count["cleanup"] += 1
            if call_count["cleanup"] > 2:
                # After a few calls, raise an error
                raise ValueError(f"Cleanup error {call_count['cleanup']}")
            return []

        # Patch at the correct module level
        with (
            patch(
                "custom_components.retention_cleaner.coordinator.Path.glob",
                side_effect=track_scan_calls,
            ),
            patch(
                "custom_components.retention_cleaner.coordinator.Path.unlink",
                side_effect=track_cleanup_calls,
            ),
        ):
            # Run multiple operations in parallel
            tasks = [
                coordinator.async_run_scan_now(),
                coordinator.async_run_scan_now(),
                coordinator.async_run_cleanup_now(),
                coordinator.async_run_cleanup_now(),
                coordinator.async_run_scan_now(),  # This should fail
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check that some operations succeeded and some failed
            successes = [r for r in results if not isinstance(r, Exception)]
            failures = [r for r in results if isinstance(r, Exception)]

            assert len(successes) >= 2  # At least 2 should succeed
            assert len(failures) >= 1  # At least 1 should fail

            # Verify errors are properly wrapped
            for failure in failures:
                if isinstance(failure, UpdateFailed):
                    assert "failed:" in str(failure).lower()

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_exception_during_resource_cleanup(
    hass: HomeAssistant, init_integration_no_glob_mock
):
    """Test that exceptions during resource cleanup are handled gracefully.

    Verifies coordinator shutdown works even if cleanup operations fail.
    """
    config_entry = init_integration_no_glob_mock
    coordinator = config_entry.runtime_data

    # Mock the cleanup to fail
    with patch.object(
        coordinator,
        "_async_cleanup_folder",
        side_effect=RuntimeError("Cleanup failed during shutdown"),
    ):
        # This should not raise even though cleanup fails
        await coordinator.async_shutdown()

        # Verify timers are cleaned up despite the error
        assert coordinator._unsub_daily is None
        assert coordinator._unsub_refresh is None


async def test_disk_full_error_handling(
    hass: HomeAssistant, init_integration_no_glob_mock
):
    """Test handling of disk full errors during cleanup.

    These are critical errors that should abort operation immediately.
    """
    import errno

    config_entry = init_integration_no_glob_mock
    coordinator = config_entry.runtime_data

    try:
        # Create OSError with ENOSPC (disk full)
        disk_full_error = OSError(errno.ENOSPC, "No space left on device")
        disk_full_error.errno = errno.ENOSPC

        with (
            patch(
                "custom_components.retention_cleaner.coordinator.Path.unlink",
                side_effect=disk_full_error,
            ),
            patch(
                "custom_components.retention_cleaner.coordinator.Path.glob",
                return_value=[Mock(name=f"file{i}.txt") for i in range(5)],
            ),
        ):
            exc_info = await assert_exception_chain(
                coordinator.async_run_cleanup_now, UpdateFailed, "Cleanup failed:"
            )

            # The error should mention disk full
            error_str = str(exc_info.value).lower()
            assert "space" in error_str or "disk" in error_str

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_memory_error_handling(
    hass: HomeAssistant, init_integration_no_glob_mock
):
    """Test handling of memory errors during large directory scans.

    Simulates out-of-memory conditions when processing huge directories.
    """
    config_entry = init_integration_no_glob_mock
    coordinator = config_entry.runtime_data

    try:

        def raise_memory_error(*args, **kwargs):
            raise MemoryError("Out of memory processing large directory")

        with patch(
            "custom_components.retention_cleaner.coordinator.Path.glob",
            side_effect=raise_memory_error,
        ):
            exc_info = await assert_exception_chain(
                coordinator.async_run_scan_now, UpdateFailed, "Scan failed:"
            )

            assert "memory" in str(exc_info.value).lower()

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    "exception_class,expected_message",
    [
        (KeyboardInterrupt, "interrupted"),
        (SystemExit, "system"),
        (GeneratorExit, "generator"),
        (StopAsyncIteration, "iteration"),
    ],
)
async def test_critical_exceptions_propagation(
    hass: HomeAssistant,
    init_integration_no_glob_mock,
    exception_class,
    expected_message,
):
    """Test that critical exceptions are properly wrapped and propagated.

    Some exceptions like KeyboardInterrupt should be handled specially.
    """
    config_entry = init_integration_no_glob_mock
    coordinator = config_entry.runtime_data

    try:
        with (
            patch(
                "custom_components.retention_cleaner.coordinator.Path.glob",
                side_effect=exception_class("Critical error"),
            ),
            pytest.raises(UpdateFailed),
        ):
            await coordinator.async_run_cleanup_now()

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()
