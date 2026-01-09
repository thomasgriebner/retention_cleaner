"""Test retention_cleaner sensor entities."""

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.retention_cleaner.const import DOMAIN


async def test_sensor_setup(hass: HomeAssistant, init_integration):
    """Test sensor entities are created correctly."""
    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state is not None
    assert state.state == "0"  # Initial value

    state = hass.states.get("sensor.test_cleanup_files_older_than_retention")
    assert state is not None

    state = hass.states.get("sensor.test_cleanup_deleted_last_cleanup")
    assert state is not None


async def test_sensor_attributes(hass: HomeAssistant, init_integration):
    """Test sensor attributes and device classes."""
    registry = er.async_get(hass)

    entry = registry.async_get("sensor.test_cleanup_total_files")
    assert entry is not None
    assert entry.unique_id == f"{init_integration.entry_id}_total_files"

    entry = registry.async_get("sensor.test_cleanup_deleted_bytes_last_cleanup")
    assert entry is not None
    assert entry.unique_id == f"{init_integration.entry_id}_deleted_bytes_last_run"
    state = hass.states.get("sensor.test_cleanup_deleted_bytes_last_cleanup")
    assert state is not None
    assert state.attributes.get("device_class") == SensorDeviceClass.DATA_SIZE
    assert state.attributes.get("unit_of_measurement") == UnitOfInformation.BYTES

    entry = registry.async_get("sensor.test_cleanup_last_scan")
    assert entry is not None
    state = hass.states.get("sensor.test_cleanup_last_scan")
    assert state.attributes.get("device_class") == SensorDeviceClass.TIMESTAMP


async def test_sensor_updates_from_coordinator(hass: HomeAssistant, init_integration):
    """Test that sensors update when coordinator data changes."""
    coordinator = init_integration.runtime_data.coordinator

    coordinator.data = {
        "total_files": 100,
        "older_than_retention": 25,
        "deleted_last_run": 10,
        "deleted_bytes_last_run": 102400,
        "last_scan": "2024-01-01T12:00:00",
        "last_cleanup": "2024-01-01T02:00:00",
        "last_scan_duration_ms": 150.5,
        "last_cleanup_duration_ms": 500.2,
    }

    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state.state == "100"

    state = hass.states.get("sensor.test_cleanup_files_older_than_retention")
    assert state.state == "25"

    state = hass.states.get("sensor.test_cleanup_deleted_last_cleanup")
    assert state.state == "10"

    state = hass.states.get("sensor.test_cleanup_deleted_bytes_last_cleanup")
    assert state.state == "102400"

    state = hass.states.get("sensor.test_cleanup_last_scan")
    assert state.state == "2024-01-01T12:00:00"


async def test_performance_sensors(hass: HomeAssistant, init_integration):
    """Test performance tracking sensors."""
    coordinator = init_integration.runtime_data.coordinator

    coordinator.data = {
        "last_scan_duration_ms": 150.5,
        "last_cleanup_duration_ms": 500.2,
    }

    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_last_scan_duration")
    assert state is not None
    assert state.state == "150.5"
    assert state.attributes.get("device_class") == SensorDeviceClass.DURATION
    assert state.attributes.get("unit_of_measurement") == "ms"
    assert state.attributes.get("state_class") == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.test_cleanup_last_cleanup_duration")
    assert state is not None
    assert state.state == "500.2"


async def test_sensor_availability(hass: HomeAssistant, init_integration):
    """Test sensor availability based on coordinator."""
    coordinator = init_integration.runtime_data.coordinator

    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state.state != "unavailable"

    coordinator.last_update_success = False
    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state.state == "unavailable"


async def test_sensor_device_info(hass: HomeAssistant, init_integration):
    """Test that sensors are linked to the correct device."""
    registry = er.async_get(hass)

    entry = registry.async_get("sensor.test_cleanup_total_files")
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


async def test_diagnostic_sensors(hass: HomeAssistant, init_integration):
    """Test that diagnostic sensors have correct category."""
    registry = er.async_get(hass)

    diagnostic_sensors = [
        "sensor.test_cleanup_last_scan",
        "sensor.test_cleanup_last_cleanup",
        "sensor.test_cleanup_last_scan_duration",
        "sensor.test_cleanup_last_cleanup_duration",
    ]

    for sensor_id in diagnostic_sensors:
        entry = registry.async_get(sensor_id)
        assert entry is not None
        assert entry.entity_category == EntityCategory.DIAGNOSTIC


async def test_sensor_missing_data_handling(hass: HomeAssistant, init_integration):
    """Test sensors handle missing data gracefully."""
    coordinator = init_integration.runtime_data.coordinator

    coordinator.data = {
        "total_files": 50,
        # Missing most fields
    }

    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    # Should handle missing data without errors
    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state.state == "50"

    state = hass.states.get("sensor.test_cleanup_files_older_than_retention")
    assert state.state in ["0", "unknown"]  # Should have safe default

    state = hass.states.get("sensor.test_cleanup_last_scan")
    assert state.state in ["unknown", ""]  # No timestamp available


async def test_sensor_unique_ids_stable(hass: HomeAssistant, init_integration):
    """Test that sensor unique IDs remain stable."""
    registry = er.async_get(hass)
    entry_id = init_integration.entry_id

    expected_sensors = {
        "total_files": f"{entry_id}_total_files",
        "older_than_retention": f"{entry_id}_older_than_retention",
        "deleted_last_run": f"{entry_id}_deleted_last_run",
        "deleted_bytes_last_run": f"{entry_id}_deleted_bytes_last_run",
        "last_scan": f"{entry_id}_last_scan",
        "last_cleanup": f"{entry_id}_last_cleanup",
        "last_scan_duration_ms": f"{entry_id}_last_scan_duration_ms",
        "last_cleanup_duration_ms": f"{entry_id}_last_cleanup_duration_ms",
    }

    for sensor_type, expected_unique_id in expected_sensors.items():
        # Find entity by unique_id
        entity = registry.async_get_entity_id("sensor", DOMAIN, expected_unique_id)
        assert entity is not None, f"Sensor {sensor_type} not found"
