"""Test state restoration for retention cleaner sensors."""

from __future__ import annotations

from unittest.mock import Mock, patch

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
import pytest


def create_mock_last_state(state_value: str, attributes: dict | None = None):
    """Create a mock last_state object for testing."""
    mock_state = Mock()
    mock_state.state = state_value
    mock_state.attributes = attributes or {}
    return mock_state


async def test_sensor_restore_numeric_value(hass: HomeAssistant, mock_setup_entry):
    """Test sensor restores numeric values correctly."""
    # Create a mock state
    mock_state = create_mock_last_state(
        "42",
        {
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
        },
    )

    # Mock the async_get_last_state method before integration setup
    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=mock_state,
    ):
        # Set up integration with the mock active
        mock_setup_entry.add_to_hass(hass)

        # Clear coordinator data to force restoration
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.glob", return_value=[]),
        ):
            assert await hass.config_entries.async_setup(mock_setup_entry.entry_id)
            await hass.async_block_till_done()

            # Clear coordinator data after setup to test restoration fallback
            coordinator = mock_setup_entry.runtime_data
            coordinator.data = {}  # No current data - should use restored

            # Trigger entity state update
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        # Check restored state
        state = hass.states.get("sensor.test_cleanup_total_files")
        assert state is not None
        # The restored value should be used when no current data
        assert state.state == "42"


async def test_sensor_restore_timestamp_value(hass: HomeAssistant, mock_setup_entry):
    """Test sensor restores timestamp values correctly."""
    mock_state = create_mock_last_state(
        "2024-01-07T15:30:45", {"base_path": "/media/test"}
    )

    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=mock_state,
    ):
        mock_setup_entry.add_to_hass(hass)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.glob", return_value=[]),
        ):
            assert await hass.config_entries.async_setup(mock_setup_entry.entry_id)
            await hass.async_block_till_done()

            # Clear coordinator data to force restoration
            coordinator = mock_setup_entry.runtime_data
            coordinator.data = {}
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        # Timestamp should be restored as-is
        state = hass.states.get("sensor.test_cleanup_last_scan")
        assert state is not None
        assert state.state == "2024-01-07T15:30:45"


async def test_sensor_no_restored_state(hass: HomeAssistant, mock_setup_entry):
    """Test sensor behavior when no restored state exists."""
    # Mock no restored state
    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=None,
    ):
        mock_setup_entry.add_to_hass(hass)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.glob", return_value=[]),
        ):
            assert await hass.config_entries.async_setup(mock_setup_entry.entry_id)
            await hass.async_block_till_done()

            # Clear coordinator data
            coordinator = mock_setup_entry.runtime_data
            coordinator.data = {}
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        # Should show None when no current data and no restored state
        state = hass.states.get("sensor.test_cleanup_total_files")
        assert state is not None
        # Without restored state and no current data, falls back to None
        assert state.state in [STATE_UNAVAILABLE, "0", None, STATE_UNKNOWN]


async def test_sensor_current_data_overrides_restored(
    hass: HomeAssistant, mock_setup_entry
):
    """Test that current coordinator data overrides restored state."""
    # Mock restored state
    mock_state = create_mock_last_state("42")

    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=mock_state,
    ):
        mock_setup_entry.add_to_hass(hass)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.glob", return_value=[]),
        ):
            assert await hass.config_entries.async_setup(mock_setup_entry.entry_id)
            await hass.async_block_till_done()

            # Set coordinator with current data
            coordinator = mock_setup_entry.runtime_data
            coordinator.data = {"total_files": 123}  # Current data should win
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        # Current data should override restored state
        state = hass.states.get("sensor.test_cleanup_total_files")
        assert state is not None
        assert state.state == "123"  # Current data, not restored "42"


@pytest.mark.parametrize("invalid_state", ["", "not_a_number", "abc", "-5"])
async def test_sensor_invalid_numeric_restoration(
    hass: HomeAssistant, mock_setup_entry, invalid_state
):
    """Test sensor handles invalid restored values gracefully."""
    mock_state = create_mock_last_state(invalid_state)

    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=mock_state,
    ):
        mock_setup_entry.add_to_hass(hass)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.glob", return_value=[]),
        ):
            assert await hass.config_entries.async_setup(mock_setup_entry.entry_id)
            await hass.async_block_till_done()

            # Clear coordinator data to force restoration
            coordinator = mock_setup_entry.runtime_data
            coordinator.data = {}
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        # Should fall back to 0 for invalid numeric values
        state = hass.states.get("sensor.test_cleanup_total_files")
        assert state is not None
        assert state.state == "0"


@pytest.mark.parametrize("ignored_state", [STATE_UNKNOWN, STATE_UNAVAILABLE])
async def test_sensor_unknown_unavailable_state_ignored(
    hass: HomeAssistant, mock_setup_entry, ignored_state
):
    """Test that unknown/unavailable states are ignored during restoration."""
    mock_state = create_mock_last_state(ignored_state)

    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=mock_state,
    ):
        mock_setup_entry.add_to_hass(hass)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.glob", return_value=[]),
        ):
            assert await hass.config_entries.async_setup(mock_setup_entry.entry_id)
            await hass.async_block_till_done()

            # Clear coordinator data to force restoration
            coordinator = mock_setup_entry.runtime_data
            coordinator.data = {}
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        # Should ignore unknown/unavailable and return None
        state = hass.states.get("sensor.test_cleanup_total_files")
        assert state is not None
        # Should not restore the unknown/unavailable value
        assert state.state != ignored_state


async def test_binary_sensor_restore_on_state(hass: HomeAssistant, mock_setup_entry):
    """Test binary sensor restores 'on' state correctly."""
    mock_state = create_mock_last_state("on")

    with patch(
        "custom_components.retention_cleaner.binary_sensor.RetentionCleanerPathAvailable.async_get_last_state",
        return_value=mock_state,
    ):
        mock_setup_entry.add_to_hass(hass)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.glob", return_value=[]),
        ):
            assert await hass.config_entries.async_setup(mock_setup_entry.entry_id)
            await hass.async_block_till_done()

            # Clear coordinator data to force restoration
            coordinator = mock_setup_entry.runtime_data
            coordinator.data = {}
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        # Should restore the on state
        state = hass.states.get("binary_sensor.test_cleanup_path_available")
        assert state is not None
        assert state.state == "on"


async def test_binary_sensor_restore_off_state(hass: HomeAssistant, mock_setup_entry):
    """Test binary sensor restores 'off' state correctly."""
    mock_state = create_mock_last_state("off")

    with patch(
        "custom_components.retention_cleaner.binary_sensor.RetentionCleanerPathAvailable.async_get_last_state",
        return_value=mock_state,
    ):
        mock_setup_entry.add_to_hass(hass)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.glob", return_value=[]),
        ):
            assert await hass.config_entries.async_setup(mock_setup_entry.entry_id)
            await hass.async_block_till_done()

            # Clear coordinator data to force restoration
            coordinator = mock_setup_entry.runtime_data
            coordinator.data = {}
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        # Should restore the off state
        state = hass.states.get("binary_sensor.test_cleanup_path_available")
        assert state is not None
        assert state.state == "off"


async def test_binary_sensor_current_data_overrides_restored(
    hass: HomeAssistant, mock_setup_entry
):
    """Test that current coordinator data overrides restored state for binary sensor."""
    # Mock restored state as off
    mock_state = create_mock_last_state("off")

    with patch(
        "custom_components.retention_cleaner.binary_sensor.RetentionCleanerPathAvailable.async_get_last_state",
        return_value=mock_state,
    ):
        mock_setup_entry.add_to_hass(hass)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.glob", return_value=[]),
        ):
            assert await hass.config_entries.async_setup(mock_setup_entry.entry_id)
            await hass.async_block_till_done()

            # Set coordinator with current data
            coordinator = mock_setup_entry.runtime_data
            coordinator.data = {"path_available": True}  # Current data should win
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        # Current data should override restored state
        state = hass.states.get("binary_sensor.test_cleanup_path_available")
        assert state is not None
        assert state.state == "on"  # Current data, not restored "off"


async def test_binary_sensor_no_restored_state(hass: HomeAssistant, mock_setup_entry):
    """Test binary sensor behavior when no restored state exists."""
    # Mock no restored state
    with patch(
        "custom_components.retention_cleaner.binary_sensor.RetentionCleanerPathAvailable.async_get_last_state",
        return_value=None,
    ):
        mock_setup_entry.add_to_hass(hass)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.glob", return_value=[]),
        ):
            assert await hass.config_entries.async_setup(mock_setup_entry.entry_id)
            await hass.async_block_till_done()

            # Clear coordinator data
            coordinator = mock_setup_entry.runtime_data
            coordinator.data = {}
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        # Should show None when no data and no restored state
        state = hass.states.get("binary_sensor.test_cleanup_path_available")
        assert state is not None
        assert state.state in [STATE_UNAVAILABLE, None]


@pytest.mark.parametrize("ignored_state", [STATE_UNKNOWN, STATE_UNAVAILABLE])
async def test_binary_sensor_unknown_state_ignored(
    hass: HomeAssistant, mock_setup_entry, ignored_state
):
    """Test that unknown/unavailable states are ignored for binary sensor."""
    mock_state = create_mock_last_state(ignored_state)

    with patch(
        "custom_components.retention_cleaner.binary_sensor.RetentionCleanerPathAvailable.async_get_last_state",
        return_value=mock_state,
    ):
        mock_setup_entry.add_to_hass(hass)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.glob", return_value=[]),
        ):
            assert await hass.config_entries.async_setup(mock_setup_entry.entry_id)
            await hass.async_block_till_done()

            # Clear coordinator data
            coordinator = mock_setup_entry.runtime_data
            coordinator.data = {}
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        # Should ignore unknown/unavailable states
        state = hass.states.get("binary_sensor.test_cleanup_path_available")
        assert state is not None
        assert state.state != ignored_state


async def test_attribute_restoration_priority(hass: HomeAssistant, mock_setup_entry):
    """Test that current attributes override restored ones correctly."""
    # Mock restored state with different attributes
    mock_state = create_mock_last_state(
        "10",
        {
            "base_path": "/media/old_path",
            "pattern": "*.old",
            "retention_days": 3,
        },
    )

    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=mock_state,
    ):
        mock_setup_entry.add_to_hass(hass)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.glob", return_value=[]),
        ):
            assert await hass.config_entries.async_setup(mock_setup_entry.entry_id)
            await hass.async_block_till_done()

            # Set coordinator with current attributes
            coordinator = mock_setup_entry.runtime_data
            coordinator.data = {
                "total_files": 50,
                "base_path": "/media/current",
                "pattern": "*.new",
                "retention_days": 7,
            }
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        # Current attributes should take precedence
        state = hass.states.get("sensor.test_cleanup_total_files")
        assert state is not None
        assert state.state == "50"  # Current value
        assert state.attributes["base_path"] == "/media/current"
        assert state.attributes["pattern"] == "*.new"
        assert state.attributes["retention_days"] == 7


async def test_restoration_exception_handling(hass: HomeAssistant, mock_setup_entry):
    """Test graceful handling of restoration failures."""
    # Mock async_get_last_state to raise an exception
    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        side_effect=Exception("Restore failed"),
    ):
        mock_setup_entry.add_to_hass(hass)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.glob", return_value=[]),
        ):
            # Should not crash during setup
            assert await hass.config_entries.async_setup(mock_setup_entry.entry_id)
            await hass.async_block_till_done()

        # Integration should still work normally without restoration
        state = hass.states.get("sensor.test_cleanup_total_files")
        assert state is not None
        # Should show current state or None, not crash
