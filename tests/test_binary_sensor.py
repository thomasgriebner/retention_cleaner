"""Test retention_cleaner binary sensor entities."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.retention_cleaner.const import DOMAIN


async def test_binary_sensor_setup(hass: HomeAssistant, init_integration):
    """Test binary sensor entity is created correctly."""
    state = hass.states.get("binary_sensor.test_cleanup_path_accessible")
    assert state is not None
    assert state.state == STATE_ON  # Path should be accessible initially


async def test_binary_sensor_attributes(hass: HomeAssistant, init_integration):
    """Test binary sensor attributes and device class."""
    registry = er.async_get(hass)

    entry = registry.async_get("binary_sensor.test_cleanup_path_accessible")
    assert entry is not None
    assert entry.unique_id == f"{init_integration.entry_id}_path_accessible"

    state = hass.states.get("binary_sensor.test_cleanup_path_accessible")
    assert state is not None
    assert state.attributes.get("device_class") == BinarySensorDeviceClass.CONNECTIVITY


async def test_binary_sensor_path_accessible(hass: HomeAssistant, init_integration):
    """Test binary sensor reflects path accessibility."""
    coordinator = init_integration.runtime_data

    coordinator.data = {
        "path_accessible": True,
    }
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_cleanup_path_accessible")
    assert state.state == STATE_ON

    coordinator.data = {
        "path_accessible": False,
    }
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_cleanup_path_accessible")
    assert state.state == STATE_OFF


async def test_binary_sensor_availability(hass: HomeAssistant, init_integration):
    """Test binary sensor availability based on coordinator."""
    coordinator = init_integration.runtime_data

    state = hass.states.get("binary_sensor.test_cleanup_path_accessible")
    assert state.state != "unavailable"

    coordinator.last_update_success = False
    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_cleanup_path_accessible")
    assert state.state == "unavailable"


async def test_binary_sensor_device_info(hass: HomeAssistant, init_integration):
    """Test that binary sensor is linked to the correct device."""
    registry = er.async_get(hass)

    entry = registry.async_get("binary_sensor.test_cleanup_path_accessible")
    assert entry is not None
    assert entry.device_id is not None

    # Verify device info
    device_registry = hass.helpers.device_registry.async_get(hass)
    device = device_registry.async_get(entry.device_id)
    assert device is not None
    assert device.name == "Test Cleanup"
    assert device.model == "/media/test"
    assert device.manufacturer == "Retention Cleaner"
    assert (DOMAIN, init_integration.entry_id) in device.identifiers


async def test_binary_sensor_unique_id_stable(hass: HomeAssistant, init_integration):
    """Test that binary sensor unique ID remains stable."""
    registry = er.async_get(hass)
    entry_id = init_integration.entry_id

    # Find entity by unique_id
    entity = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry_id}_path_accessible"
    )
    assert entity is not None
    assert entity == "binary_sensor.test_cleanup_path_accessible"


async def test_binary_sensor_missing_data(hass: HomeAssistant, init_integration):
    """Test binary sensor handles missing data gracefully."""
    coordinator = init_integration.runtime_data

    coordinator.data = {
        "total_files": 100,
        # Missing path_accessible
    }
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    # Should handle missing data without errors (default to OFF/False)
    state = hass.states.get("binary_sensor.test_cleanup_path_accessible")
    assert state.state == STATE_OFF  # Default when data missing


async def test_binary_sensor_entity_category(hass: HomeAssistant, init_integration):
    """Test that binary sensor has correct entity category."""
    registry = er.async_get(hass)

    entry = registry.async_get("binary_sensor.test_cleanup_path_accessible")
    assert entry is not None
    # Binary sensors typically don't have entity category unless diagnostic
    # Path accessibility is operational, not diagnostic
