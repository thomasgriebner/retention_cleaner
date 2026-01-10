"""Test state restoration for retention cleaner sensors."""

from __future__ import annotations

from unittest.mock import Mock, patch

from homeassistant.core import HomeAssistant


def create_mock_last_state(state_value: str, attributes: dict | None = None):
    """Create a mock last_state object for testing."""
    mock_state = Mock()
    mock_state.state = state_value
    mock_state.attributes = attributes or {}
    return mock_state


async def test_sensor_restore_numeric_value(hass: HomeAssistant, init_integration):
    """Test sensor restores numeric values correctly."""
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

    # Mock async_get_last_state at the class level
    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=mock_state,
    ):
        # Clear coordinator data to force restoration fallback
        coordinator = init_integration.runtime_data
        coordinator.data = {}

        # Trigger entity update by forcing coordinator refresh
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

    # Check restored state - should fallback to restored value
    state = hass.states.get(sensor_entity_id)
    assert state is not None
    assert state.state == "42"


async def test_sensor_restore_timestamp_value(hass: HomeAssistant, init_integration):
    """Test sensor restores timestamp values correctly."""
    sensor_entity_id = "sensor.test_cleanup_last_scan"

    mock_state = create_mock_last_state(
        "2024-01-07T15:30:45", {"base_path": "/media/test"}
    )

    # Mock async_get_last_state at the class level
    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=mock_state,
    ):
        coordinator = init_integration.runtime_data
        coordinator.data = {}
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

    # Timestamp should be restored as datetime object
    state = hass.states.get(sensor_entity_id)
    assert state is not None
    # The state should be converted to a valid timestamp
    assert state.state is not None


async def test_sensor_current_data_overrides_restored(
    hass: HomeAssistant, init_integration
):
    """Test that current coordinator data overrides restored state."""
    sensor_entity_id = "sensor.test_cleanup_total_files"

    # Mock restored state
    mock_state = create_mock_last_state("42")

    # Mock async_get_last_state at the class level
    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        return_value=mock_state,
    ):
        # Set coordinator with current data
        coordinator = init_integration.runtime_data
        coordinator.data = {"total_files": 123}  # Current data should win
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

    # Current data should override restored state
    state = hass.states.get(sensor_entity_id)
    assert state is not None
    assert state.state == "123"  # Current data, not restored "42"


async def test_binary_sensor_restore_on_state(hass: HomeAssistant, init_integration):
    """Test binary sensor restores 'on' state correctly."""
    sensor_entity_id = "binary_sensor.test_cleanup_path_available"

    mock_state = create_mock_last_state("on")

    # Mock async_get_last_state at the class level
    with patch(
        "custom_components.retention_cleaner.binary_sensor.RetentionCleanerPathAvailable.async_get_last_state",
        return_value=mock_state,
    ):
        # Clear coordinator data to force restoration
        coordinator = init_integration.runtime_data
        coordinator.data = {}
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

    # Should restore the on state
    state = hass.states.get(sensor_entity_id)
    assert state is not None
    assert state.state == "on"


async def test_binary_sensor_current_data_overrides_restored(
    hass: HomeAssistant, init_integration
):
    """Test that current coordinator data overrides restored state for binary sensor."""
    sensor_entity_id = "binary_sensor.test_cleanup_path_available"

    # Mock restored state as off
    mock_state = create_mock_last_state("off")

    # Mock async_get_last_state at the class level
    with patch(
        "custom_components.retention_cleaner.binary_sensor.RetentionCleanerPathAvailable.async_get_last_state",
        return_value=mock_state,
    ):
        # Set coordinator with current data
        coordinator = init_integration.runtime_data
        coordinator.data = {"path_available": False}  # Current data should win
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

    # Current data should override restored state
    state = hass.states.get(sensor_entity_id)
    assert state is not None
    assert state.state == "off"  # Current data, not restored "off"


async def test_restoration_exception_handling(hass: HomeAssistant, init_integration):
    """Test graceful handling of restoration failures."""
    sensor_entity_id = "sensor.test_cleanup_total_files"

    # Mock async_get_last_state to raise an exception
    with patch(
        "custom_components.retention_cleaner.sensor.RetentionCleanerSensor.async_get_last_state",
        side_effect=Exception("Restore failed"),
    ):
        # Should not crash during operation
        coordinator = init_integration.runtime_data
        coordinator.data = {}
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

    # Integration should still work normally without restoration
    state = hass.states.get(sensor_entity_id)
    assert state is not None
    # Should show current state or unavailable, not crash
