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


async def test_sensor_restore_numeric_value(hass: HomeAssistant, init_integration):
    """Test sensor restores numeric values correctly."""
    # Get the sensor entity directly
    sensor_entity_id = "sensor.test_cleanup_total_files"

    # Create a mock state
    mock_state = create_mock_last_state(
        "42",
        {
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
        },
    )

    # Mock the async_get_last_state method on the actual sensor
    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=mock_state,
    ):
        # Reload integration to trigger restoration
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Check restored state
        state = hass.states.get(sensor_entity_id)
        assert state is not None
        # The restored value should be used when no current data
        assert state.state == "42"


async def test_sensor_restore_timestamp_value(hass: HomeAssistant, init_integration):
    """Test sensor restores timestamp values correctly."""
    sensor_entity_id = "sensor.test_cleanup_last_scan"

    mock_state = create_mock_last_state(
        "2024-01-07T15:30:45", {"base_path": "/media/test"}
    )

    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=mock_state,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Timestamp should be restored as-is
        state = hass.states.get(sensor_entity_id)
        assert state is not None
        assert state.state == "2024-01-07T15:30:45"


async def test_sensor_no_restored_state(hass: HomeAssistant, init_integration):
    """Test sensor behavior when no restored state exists."""
    sensor_entity_id = "sensor.test_cleanup_total_files"

    # Mock no restored state
    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=None,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Should show unavailable/None when no current data and no restored state
        state = hass.states.get(sensor_entity_id)
        assert state is not None
        # Without restored state and no current data, should be None or 0
        assert state.state in [STATE_UNAVAILABLE, "0", None, STATE_UNKNOWN]


async def test_sensor_current_data_overrides_restored(
    hass: HomeAssistant, init_integration
):
    """Test that current coordinator data overrides restored state."""
    sensor_entity_id = "sensor.test_cleanup_total_files"

    # Set up coordinator with current data
    coordinator = init_integration.runtime_data
    coordinator.data = {"total_files": 123}  # Current data should win

    # Mock restored state
    mock_state = create_mock_last_state("42")

    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=mock_state,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Current data should override restored state
        state = hass.states.get(sensor_entity_id)
        assert state is not None
        assert state.state == "123"  # Current data, not restored "42"


@pytest.mark.parametrize("invalid_state", ["", "not_a_number", "abc", "-5"])
async def test_sensor_invalid_numeric_restoration(
    hass: HomeAssistant, init_integration, invalid_state
):
    """Test sensor handles invalid restored values gracefully."""
    sensor_entity_id = "sensor.test_cleanup_total_files"

    mock_state = create_mock_last_state(invalid_state)

    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=mock_state,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Should fall back to 0 for invalid numeric values
        state = hass.states.get(sensor_entity_id)
        assert state is not None
        assert state.state == "0"


@pytest.mark.parametrize("ignored_state", [STATE_UNKNOWN, STATE_UNAVAILABLE])
async def test_sensor_unknown_unavailable_state_ignored(
    hass: HomeAssistant, init_integration, ignored_state
):
    """Test that unknown/unavailable states are ignored during restoration."""
    sensor_entity_id = "sensor.test_cleanup_total_files"

    mock_state = create_mock_last_state(ignored_state)

    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=mock_state,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Should ignore unknown/unavailable and show current state
        state = hass.states.get(sensor_entity_id)
        assert state is not None
        # Should not restore the unknown/unavailable value
        assert state.state != ignored_state


async def test_binary_sensor_restore_on_state(hass: HomeAssistant, init_integration):
    """Test binary sensor restores 'on' state correctly."""
    sensor_entity_id = "binary_sensor.test_cleanup_path_available"

    mock_state = create_mock_last_state("on")

    with patch(
        "custom_components.retention_cleaner.binary_sensor.RetentionCleanerPathAvailable.async_get_last_state",
        return_value=mock_state,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Should restore the on state
        state = hass.states.get(sensor_entity_id)
        assert state is not None
        assert state.state == "on"


async def test_binary_sensor_restore_off_state(hass: HomeAssistant, init_integration):
    """Test binary sensor restores 'off' state correctly."""
    sensor_entity_id = "binary_sensor.test_cleanup_path_available"

    mock_state = create_mock_last_state("off")

    with patch(
        "custom_components.retention_cleaner.binary_sensor.RetentionCleanerPathAvailable.async_get_last_state",
        return_value=mock_state,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Should restore the off state
        state = hass.states.get(sensor_entity_id)
        assert state is not None
        assert state.state == "off"


async def test_binary_sensor_current_data_overrides_restored(
    hass: HomeAssistant, init_integration
):
    """Test that current coordinator data overrides restored state for binary sensor."""
    sensor_entity_id = "binary_sensor.test_cleanup_path_available"

    # Set up coordinator with current data
    coordinator = init_integration.runtime_data
    coordinator.data = {"path_available": True}  # Current data should win

    # Mock restored state as off
    mock_state = create_mock_last_state("off")

    with patch(
        "custom_components.retention_cleaner.binary_sensor.RetentionCleanerPathAvailable.async_get_last_state",
        return_value=mock_state,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Current data should override restored state
        state = hass.states.get(sensor_entity_id)
        assert state is not None
        assert state.state == "on"  # Current data, not restored "off"


async def test_binary_sensor_no_restored_state(hass: HomeAssistant, init_integration):
    """Test binary sensor behavior when no restored state exists."""
    sensor_entity_id = "binary_sensor.test_cleanup_path_available"

    # Mock no restored state
    with patch(
        "custom_components.retention_cleaner.binary_sensor.RetentionCleanerPathAvailable.async_get_last_state",
        return_value=None,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Should show unavailable when no data and no restored state
        state = hass.states.get(sensor_entity_id)
        assert state is not None
        assert state.state in [STATE_UNAVAILABLE, "off", STATE_UNKNOWN]


@pytest.mark.parametrize("ignored_state", [STATE_UNKNOWN, STATE_UNAVAILABLE])
async def test_binary_sensor_unknown_state_ignored(
    hass: HomeAssistant, init_integration, ignored_state
):
    """Test that unknown/unavailable states are ignored for binary sensor."""
    sensor_entity_id = "binary_sensor.test_cleanup_path_available"

    mock_state = create_mock_last_state(ignored_state)

    with patch(
        "custom_components.retention_cleaner.binary_sensor.RetentionCleanerPathAvailable.async_get_last_state",
        return_value=mock_state,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Should ignore unknown/unavailable states
        state = hass.states.get(sensor_entity_id)
        assert state is not None
        assert state.state != ignored_state


async def test_attribute_restoration_priority(hass: HomeAssistant, init_integration):
    """Test that current attributes override restored ones correctly."""
    sensor_entity_id = "sensor.test_cleanup_total_files"

    # Set up coordinator with current attributes
    coordinator = init_integration.runtime_data
    coordinator.data = {
        "total_files": 50,
        "base_path": "/media/current",
        "pattern": "*.new",
        "retention_days": 7,
    }

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
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Current attributes should take precedence
        state = hass.states.get(sensor_entity_id)
        assert state is not None
        assert state.state == "50"  # Current value
        assert state.attributes["base_path"] == "/media/current"
        assert state.attributes["pattern"] == "*.new"
        assert state.attributes["retention_days"] == 7


async def test_restoration_exception_handling(hass: HomeAssistant, init_integration):
    """Test graceful handling of restoration failures."""
    sensor_entity_id = "sensor.test_cleanup_total_files"

    # Mock async_get_last_state to raise an exception
    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        side_effect=Exception("Restore failed"),
    ):
        # Should not crash during setup
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Integration should still work normally without restoration
        state = hass.states.get(sensor_entity_id)
        assert state is not None
        # Should show current state or unavailable, not crash


async def test_partial_attribute_restoration(hass: HomeAssistant, init_integration):
    """Test restoration when only some attributes are available."""
    sensor_entity_id = "sensor.test_cleanup_total_files"

    # Mock restored state with partial attributes
    mock_state = create_mock_last_state(
        "25",
        {
            "base_path": "/media/restored",
            # Missing pattern and retention_days
        },
    )

    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=mock_state,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Verify partial restoration works
        state = hass.states.get(sensor_entity_id)
        assert state is not None
        assert state.state == "25"
        assert state.attributes["base_path"] == "/media/restored"
        # Missing attributes should be None/empty
        assert state.attributes.get("pattern") is None
        assert state.attributes.get("retention_days") is None
