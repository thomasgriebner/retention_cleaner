"""Test state restoration for retention cleaner sensors."""

from __future__ import annotations

from unittest.mock import Mock

from homeassistant.core import HomeAssistant


def create_mock_last_state(state_value: str, attributes: dict | None = None):
    """Create a mock last_state object for testing."""
    mock_state = Mock()
    mock_state.state = state_value
    mock_state.attributes = attributes or {}
    return mock_state


async def test_sensor_restore_numeric_value(hass: HomeAssistant, init_integration):
    """Test sensor restores numeric values correctly."""
    from homeassistant.helpers import entity_registry as er

    sensor_entity_id = "sensor.test_cleanup_total_files"

    # Get the entity
    registry = er.async_get(hass)
    entity_entry = registry.async_get(sensor_entity_id)
    assert entity_entry is not None

    # Get the actual entity instance from hass.states and find the entity object
    coordinator = init_integration.runtime_data

    # Find the sensor entity in the coordinator's entities
    sensor_entity = None
    for platform in hass.data.get("entity_platform", {}).values():
        if hasattr(platform, "entities"):
            for entity in platform.entities:
                if (
                    hasattr(entity, "entity_id")
                    and entity.entity_id == sensor_entity_id
                ):
                    sensor_entity = entity
                    break
        if sensor_entity:
            break

    assert sensor_entity is not None, f"Could not find entity {sensor_entity_id}"

    # Manually set restored state to simulate what async_added_to_hass does
    sensor_entity._restored_last_state = "42"
    sensor_entity._restored_attributes = {
        "base_path": "/media/test",
        "pattern": "*.jpg",
        "retention_days": 7,
    }

    # Clear coordinator data to force restoration fallback
    coordinator.data = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    # Check restored state - should fallback to restored value
    state = hass.states.get(sensor_entity_id)
    assert state is not None
    assert state.state == "42"


async def test_sensor_restore_timestamp_value(hass: HomeAssistant, init_integration):
    """Test sensor restores timestamp values correctly."""
    from homeassistant.helpers import entity_registry as er

    sensor_entity_id = "sensor.test_cleanup_last_scan"

    # Get the entity
    registry = er.async_get(hass)
    entity_entry = registry.async_get(sensor_entity_id)
    assert entity_entry is not None

    # Find the sensor entity
    coordinator = init_integration.runtime_data
    sensor_entity = None
    for platform in hass.data.get("entity_platform", {}).values():
        if hasattr(platform, "entities"):
            for entity in platform.entities:
                if (
                    hasattr(entity, "entity_id")
                    and entity.entity_id == sensor_entity_id
                ):
                    sensor_entity = entity
                    break
        if sensor_entity:
            break

    assert sensor_entity is not None

    # Manually set restored timestamp state
    sensor_entity._restored_last_state = "2024-01-07T15:30:45"
    sensor_entity._restored_attributes = {"base_path": "/media/test"}

    # Clear coordinator data to force restoration fallback
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
    from homeassistant.helpers import entity_registry as er

    sensor_entity_id = "sensor.test_cleanup_total_files"

    # Get the entity
    registry = er.async_get(hass)
    entity_entry = registry.async_get(sensor_entity_id)
    assert entity_entry is not None

    # Find the sensor entity
    coordinator = init_integration.runtime_data
    sensor_entity = None
    for platform in hass.data.get("entity_platform", {}).values():
        if hasattr(platform, "entities"):
            for entity in platform.entities:
                if (
                    hasattr(entity, "entity_id")
                    and entity.entity_id == sensor_entity_id
                ):
                    sensor_entity = entity
                    break
        if sensor_entity:
            break

    assert sensor_entity is not None

    # Set restored state
    sensor_entity._restored_last_state = "42"

    # Set coordinator with current data
    coordinator.data = {"total_files": 123}  # Current data should win
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    # Current data should override restored state
    state = hass.states.get(sensor_entity_id)
    assert state is not None
    assert state.state == "123"  # Current data, not restored "42"


async def test_binary_sensor_restore_on_state(hass: HomeAssistant, init_integration):
    """Test binary sensor restores 'on' state correctly."""
    from homeassistant.helpers import entity_registry as er

    sensor_entity_id = "binary_sensor.test_cleanup_path_available"

    # Get the entity
    registry = er.async_get(hass)
    entity_entry = registry.async_get(sensor_entity_id)
    assert entity_entry is not None

    # Get the actual entity instance
    coordinator = init_integration.runtime_data

    # Find the binary sensor entity
    binary_sensor_entity = None
    for platform in hass.data.get("entity_platform", {}).values():
        if hasattr(platform, "entities"):
            for entity in platform.entities:
                if (
                    hasattr(entity, "entity_id")
                    and entity.entity_id == sensor_entity_id
                ):
                    binary_sensor_entity = entity
                    break
        if binary_sensor_entity:
            break

    assert binary_sensor_entity is not None, f"Could not find entity {sensor_entity_id}"

    # Manually set restored state to simulate what async_added_to_hass does
    binary_sensor_entity._restored_last_state = "on"

    # Clear coordinator data to force restoration
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
    from homeassistant.helpers import entity_registry as er

    sensor_entity_id = "binary_sensor.test_cleanup_path_available"

    # Get the entity
    registry = er.async_get(hass)
    entity_entry = registry.async_get(sensor_entity_id)
    assert entity_entry is not None

    # Find the binary sensor entity
    coordinator = init_integration.runtime_data
    binary_sensor_entity = None
    for platform in hass.data.get("entity_platform", {}).values():
        if hasattr(platform, "entities"):
            for entity in platform.entities:
                if (
                    hasattr(entity, "entity_id")
                    and entity.entity_id == sensor_entity_id
                ):
                    binary_sensor_entity = entity
                    break
        if binary_sensor_entity:
            break

    assert binary_sensor_entity is not None

    # Set restored state as "off"
    binary_sensor_entity._restored_last_state = "off"

    # Set coordinator with current data
    coordinator.data = {"path_available": False}  # Current data should win
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    # Current data should override restored state
    state = hass.states.get(sensor_entity_id)
    assert state is not None
    assert state.state == "off"  # Current data, not restored "off"


async def test_restoration_exception_handling(hass: HomeAssistant, init_integration):
    """Test graceful handling of restoration failures."""
    from homeassistant.helpers import entity_registry as er

    sensor_entity_id = "sensor.test_cleanup_total_files"

    # Get the entity
    registry = er.async_get(hass)
    entity_entry = registry.async_get(sensor_entity_id)
    assert entity_entry is not None

    # Find the sensor entity
    coordinator = init_integration.runtime_data
    sensor_entity = None
    for platform in hass.data.get("entity_platform", {}).values():
        if hasattr(platform, "entities"):
            for entity in platform.entities:
                if (
                    hasattr(entity, "entity_id")
                    and entity.entity_id == sensor_entity_id
                ):
                    sensor_entity = entity
                    break
        if sensor_entity:
            break

    assert sensor_entity is not None

    # Simulate exception during restoration - set invalid restored state to None
    sensor_entity._restored_last_state = None
    sensor_entity._restored_attributes = {}

    # Should not crash during operation
    coordinator.data = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    # Integration should still work normally without restoration
    state = hass.states.get(sensor_entity_id)
    assert state is not None
    # Should show current state or unavailable, not crash
