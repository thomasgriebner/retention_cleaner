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

    state = hass.states.get("sensor.test_cleanup_older_than_retention")
    assert state is not None

    state = hass.states.get("sensor.test_cleanup_deleted_last_cleanup")
    assert state is not None


async def test_sensor_attributes(hass: HomeAssistant, init_integration):
    """Test sensor attributes and device classes."""
    registry = er.async_get(hass)

    entry = registry.async_get("sensor.test_cleanup_total_files")
    assert entry is not None
    assert entry.unique_id == f"{init_integration.entry_id}_total_files"

    entry = registry.async_get("sensor.test_cleanup_deleted_size_last_cleanup")
    assert entry is not None
    assert entry.unique_id == f"{init_integration.entry_id}_deleted_bytes_last_run"
    state = hass.states.get("sensor.test_cleanup_deleted_size_last_cleanup")
    assert state is not None
    assert state.attributes.get("device_class") == SensorDeviceClass.DATA_SIZE
    assert state.attributes.get("unit_of_measurement") == UnitOfInformation.MEGABYTES

    entry = registry.async_get("sensor.test_cleanup_last_scan")
    assert entry is not None
    state = hass.states.get("sensor.test_cleanup_last_scan")
    assert state.attributes.get("device_class") == SensorDeviceClass.TIMESTAMP


async def test_sensor_updates_from_coordinator(hass: HomeAssistant, init_integration):
    """Test that sensors update when coordinator data changes."""
    from datetime import UTC, datetime

    coordinator = init_integration.runtime_data

    coordinator.data = {
        "total_files": 100,
        "older_than_retention": 25,
        "deleted_last_run": 10,
        "deleted_bytes_last_run": 102400,
        "last_scan": datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        "last_cleanup": datetime(2024, 1, 1, 2, 0, 0, tzinfo=UTC),
        "last_scan_duration_ms": 150,
        "last_cleanup_duration_ms": 500,
    }

    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state.state == "100"

    state = hass.states.get("sensor.test_cleanup_older_than_retention")
    assert state.state == "25"

    state = hass.states.get("sensor.test_cleanup_deleted_last_cleanup")
    assert state.state == "10"

    state = hass.states.get("sensor.test_cleanup_deleted_size_last_cleanup")
    assert (
        state.state == "0.1024"
    )  # 102400 bytes = 0.1024 MB (using SI units: 1 MB = 1000000 bytes)

    state = hass.states.get("sensor.test_cleanup_last_scan")
    assert state.state == "2024-01-01T12:00:00+00:00"  # ISO format with UTC timezone


async def test_performance_sensors(hass: HomeAssistant, init_integration):
    """Test performance tracking sensors."""
    coordinator = init_integration.runtime_data

    coordinator.data = {
        "last_scan_duration_ms": 150,
        "last_cleanup_duration_ms": 500,
    }

    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_last_scan_duration")
    assert state is not None
    assert state.state == "150"  # Duration is stored as int milliseconds
    assert state.attributes.get("device_class") == SensorDeviceClass.DURATION
    assert state.attributes.get("unit_of_measurement") == "ms"
    assert state.attributes.get("state_class") == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.test_cleanup_last_cleanup_duration")
    assert state is not None
    assert state.state == "500"  # Duration is stored as int milliseconds


async def test_sensor_availability(hass: HomeAssistant, init_integration):
    """Test sensor availability based on coordinator."""
    coordinator = init_integration.runtime_data

    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state.state != "unavailable"

    # When coordinator data is None, sensors return None which becomes "unknown"
    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state.state == "unknown"  # None value becomes "unknown" in HA


async def test_sensor_device_info(hass: HomeAssistant, init_integration):
    """Test that sensors are linked to the correct device."""
    registry = er.async_get(hass)

    entry = registry.async_get("sensor.test_cleanup_total_files")
    assert entry is not None
    assert entry.device_id is not None

    # Verify device info
    # Handle HA version differences in device_registry API
    try:
        device_registry = hass.helpers.device_registry.async_get()
    except TypeError:
        # Older HA versions need hass parameter
        device_registry = hass.helpers.device_registry.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, init_integration.entry_id)}
    )
    assert device is not None
    assert device.name == "Test Cleanup"
    assert device.model == "Folder retention rule"
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
    coordinator = init_integration.runtime_data

    coordinator.data = {
        "total_files": 50,
        # Missing most fields
    }

    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    # Should handle missing data without errors
    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state.state == "50"

    state = hass.states.get("sensor.test_cleanup_older_than_retention")
    assert state.state in ["0", "unknown"]  # Should have safe default

    state = hass.states.get("sensor.test_cleanup_last_scan")
    assert state.state == "unknown"  # No timestamp available, returns None -> "unknown"


async def test_sensor_unique_ids_stable(hass: HomeAssistant, init_integration):
    """Test that sensor unique IDs remain stable."""
    registry = er.async_get(hass)
    entry_id = init_integration.entry_id

    expected_sensors = {
        "total_files": f"{entry_id}_total_files",
        "older_than_retention": f"{entry_id}_older_than_retention",
        "deleted_last_run": f"{entry_id}_deleted_last_run",
        "deleted_bytes_last_run": f"{entry_id}_deleted_bytes_last_run",
        "total_folder_size_bytes": f"{entry_id}_total_folder_size_bytes",
        "older_than_retention_size_bytes": f"{entry_id}_older_than_retention_size_bytes",
        "last_scan": f"{entry_id}_last_scan",
        "last_cleanup": f"{entry_id}_last_cleanup",
        "last_scan_duration_ms": f"{entry_id}_last_scan_duration_ms",
        "last_cleanup_duration_ms": f"{entry_id}_last_cleanup_duration_ms",
        "base_path": f"{entry_id}_base_path",
    }

    for sensor_type, expected_unique_id in expected_sensors.items():
        entity = registry.async_get_entity_id("sensor", DOMAIN, expected_unique_id)
        assert entity is not None, f"Sensor {sensor_type} not found"


async def test_sensor_restoration_exception_handling(
    hass: HomeAssistant, init_integration
):
    """Test sensor handles restoration exceptions gracefully (lines 167-170)."""
    from unittest.mock import patch

    from custom_components.retention_cleaner.sensor import RetentionCleanerSensor

    coordinator = init_integration.runtime_data

    entity = RetentionCleanerSensor(
        coordinator,
        init_integration,
        "total_files",
        "Total files",
        "files",
        "mdi:file-multiple",
    )
    entity.hass = hass
    entity.entity_id = "sensor.test_exception"

    with patch.object(
        entity,
        "async_get_last_state",
        side_effect=RuntimeError("Simulated restoration error"),
    ):
        await entity.async_added_to_hass()

    # Exception should be caught and both restored values set to None/empty dict
    assert entity._restored_last_state is None
    assert entity._restored_attributes == {}

    # Entity should still function normally
    coordinator.data = {"total_files": 42}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    assert entity.native_value == 42


async def test_sensor_restore_string_digit(hass: HomeAssistant, init_integration):
    """Test numeric sensor handles string digit restored state (line 210)."""
    from custom_components.retention_cleaner.sensor import RetentionCleanerSensor

    coordinator = init_integration.runtime_data

    entity = RetentionCleanerSensor(
        coordinator,
        init_integration,
        "total_files",
        "Total files",
        "files",
        "mdi:file-multiple",
    )
    entity.hass = hass
    entity.entity_id = "sensor.test_string_digit"

    coordinator.data = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    entity._restored_last_state = "42"
    assert entity.native_value == 42

    entity._restored_last_state = "0"
    assert entity.native_value == 0


async def test_sensor_restore_int_float_direct(hass: HomeAssistant, init_integration):
    """Test numeric sensor handles int/float restored state directly (line 212)."""
    from custom_components.retention_cleaner.sensor import RetentionCleanerSensor

    coordinator = init_integration.runtime_data

    entity = RetentionCleanerSensor(
        coordinator,
        init_integration,
        "total_files",
        "Total files",
        "files",
        "mdi:file-multiple",
    )
    entity.hass = hass
    entity.entity_id = "sensor.test_int_float"

    coordinator.data = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    entity._restored_last_state = 42
    assert entity.native_value == 42

    entity._restored_last_state = 42.7
    assert entity.native_value == 42


async def test_sensor_restore_numeric_fallback(hass: HomeAssistant, init_integration):
    """Test numeric sensor fallback to 0 for non-matching types (line 213)."""
    from custom_components.retention_cleaner.sensor import RetentionCleanerSensor

    coordinator = init_integration.runtime_data

    entity = RetentionCleanerSensor(
        coordinator,
        init_integration,
        "total_files",
        "Total files",
        "files",
        "mdi:file-multiple",
    )
    entity.hass = hass
    entity.entity_id = "sensor.test_fallback"

    coordinator.data = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    entity._restored_last_state = []
    assert entity.native_value == 0

    entity._restored_last_state = {}
    assert entity.native_value == 0

    entity._restored_last_state = None
    assert entity.native_value is None


async def test_sensor_restore_numeric_type_error(hass: HomeAssistant, init_integration):
    """Test numeric sensor handles TypeError during conversion (lines 214-215)."""
    from unittest.mock import patch

    from custom_components.retention_cleaner.sensor import RetentionCleanerSensor

    coordinator = init_integration.runtime_data

    entity = RetentionCleanerSensor(
        coordinator,
        init_integration,
        "total_files",
        "Total files",
        "files",
        "mdi:file-multiple",
    )
    entity.hass = hass
    entity.entity_id = "sensor.test_type_error"

    coordinator.data = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    entity._restored_last_state = "not_a_number"

    with patch("builtins.int", side_effect=TypeError("Conversion error")):
        assert entity.native_value == 0


async def test_sensor_restore_other_sensor_type(hass: HomeAssistant, init_integration):
    """Test sensor with non-standard key returns restored state as-is (line 218)."""
    from custom_components.retention_cleaner.sensor import RetentionCleanerSensor

    coordinator = init_integration.runtime_data

    entity = RetentionCleanerSensor(
        coordinator,
        init_integration,
        "unknown_key",
        "Unknown sensor",
        None,
        "mdi:help",
    )
    entity.hass = hass
    entity.entity_id = "sensor.test_other_type"

    coordinator.data = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    entity._restored_last_state = "custom_value_123"
    assert entity.native_value == "custom_value_123"


# ============================================================================
# FOLDER SIZE BYTE SENSORS - TDD TESTS
# ============================================================================


async def test_total_folder_size_bytes_sensor_exists_in_registry(
    hass: HomeAssistant, init_integration
):
    """Test total_folder_size_bytes sensor is created in entity registry."""
    registry = er.async_get(hass)

    entry = registry.async_get("sensor.test_cleanup_total_folder_size")
    assert entry is not None, "total_folder_size_bytes sensor should exist"
    assert (
        entry.unique_id == f"{init_integration.entry_id}_total_folder_size_bytes"
    ), "Should have correct unique_id format"


async def test_older_than_retention_size_bytes_sensor_exists_in_registry(
    hass: HomeAssistant, init_integration
):
    """Test older_than_retention_size_bytes sensor is created in entity registry."""
    registry = er.async_get(hass)

    entry = registry.async_get("sensor.test_cleanup_older_than_retention_size")
    assert entry is not None, "older_than_retention_size_bytes sensor should exist"
    assert (
        entry.unique_id
        == f"{init_integration.entry_id}_older_than_retention_size_bytes"
    ), "Should have correct unique_id format"


async def test_size_sensors_have_correct_device_class(
    hass: HomeAssistant, init_integration
):
    """Test size byte sensors have DATA_SIZE device class."""
    state_total = hass.states.get("sensor.test_cleanup_total_folder_size")
    assert state_total is not None, "total_folder_size_bytes state should exist"
    assert (
        state_total.attributes.get("device_class") == SensorDeviceClass.DATA_SIZE
    ), "Should have DATA_SIZE device class"

    state_old = hass.states.get("sensor.test_cleanup_older_than_retention_size")
    assert state_old is not None, "older_than_retention_size_bytes state should exist"
    assert (
        state_old.attributes.get("device_class") == SensorDeviceClass.DATA_SIZE
    ), "Should have DATA_SIZE device class"


async def test_size_sensors_have_correct_unit(hass: HomeAssistant, init_integration):
    """Test size byte sensors have MEGABYTES unit."""
    state_total = hass.states.get("sensor.test_cleanup_total_folder_size")
    assert state_total is not None, "total_folder_size_bytes state should exist"
    assert (
        state_total.attributes.get("unit_of_measurement") == UnitOfInformation.MEGABYTES
    ), "Should have MEGABYTES unit"

    state_old = hass.states.get("sensor.test_cleanup_older_than_retention_size")
    assert state_old is not None, "older_than_retention_size_bytes state should exist"
    assert (
        state_old.attributes.get("unit_of_measurement") == UnitOfInformation.MEGABYTES
    ), "Should have MEGABYTES unit"


async def test_size_sensors_have_correct_state_class(
    hass: HomeAssistant, init_integration
):
    """Test size byte sensors have MEASUREMENT state class."""
    state_total = hass.states.get("sensor.test_cleanup_total_folder_size")
    assert state_total is not None, "total_folder_size_bytes state should exist"
    assert (
        state_total.attributes.get("state_class") == SensorStateClass.MEASUREMENT
    ), "Should have MEASUREMENT state class"

    state_old = hass.states.get("sensor.test_cleanup_older_than_retention_size")
    assert state_old is not None, "older_than_retention_size_bytes state should exist"
    assert (
        state_old.attributes.get("state_class") == SensorStateClass.MEASUREMENT
    ), "Should have MEASUREMENT state class"


async def test_size_sensors_update_from_coordinator_data(
    hass: HomeAssistant, init_integration
):
    """Test size byte sensors update when coordinator data changes."""
    from datetime import UTC, datetime

    coordinator = init_integration.runtime_data

    coordinator.data = {
        "total_files": 100,
        "older_than_retention": 25,
        "deleted_last_run": 10,
        "deleted_bytes_last_run": 102400,
        "last_scan": datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        "last_cleanup": datetime(2024, 1, 1, 2, 0, 0, tzinfo=UTC),
        "last_scan_duration_ms": 150,
        "last_cleanup_duration_ms": 500,
        "total_folder_size_bytes": 2097152,
        "older_than_retention_size_bytes": 1048576,
    }

    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state_total = hass.states.get("sensor.test_cleanup_total_folder_size")
    assert state_total.state == "2.097152", "Should display total folder size in MB"

    state_old = hass.states.get("sensor.test_cleanup_older_than_retention_size")
    assert state_old.state == "1.048576", "Should display old files size in MB"


async def test_size_sensors_handle_missing_data(hass: HomeAssistant, init_integration):
    """Test size byte sensors handle missing data gracefully."""
    coordinator = init_integration.runtime_data

    coordinator.data = {
        "total_files": 50,
    }

    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state_total = hass.states.get("sensor.test_cleanup_total_folder_size")
    assert state_total.state in [
        "0",
        "unknown",
    ], "Should have safe default for missing total_folder_size_bytes"

    state_old = hass.states.get("sensor.test_cleanup_older_than_retention_size")
    assert state_old.state in [
        "0",
        "unknown",
    ], "Should have safe default for missing older_than_retention_size_bytes"


async def test_size_sensors_linked_to_device(hass: HomeAssistant, init_integration):
    """Test size byte sensors are linked to the correct device."""
    from custom_components.retention_cleaner.const import DOMAIN

    registry = er.async_get(hass)

    entry_total = registry.async_get("sensor.test_cleanup_total_folder_size")
    assert entry_total is not None, "total_folder_size_bytes entry should exist"
    assert entry_total.device_id is not None, "Should be linked to device"

    entry_old = registry.async_get("sensor.test_cleanup_older_than_retention_size")
    assert entry_old is not None, "older_than_retention_size_bytes entry should exist"
    assert entry_old.device_id is not None, "Should be linked to device"

    try:
        device_registry = hass.helpers.device_registry.async_get()
    except TypeError:
        device_registry = hass.helpers.device_registry.async_get(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, init_integration.entry_id)}
    )
    assert device is not None, "Device should exist"
    assert entry_total.device_id == device.id, "Should link to same device"
    assert entry_old.device_id == device.id, "Should link to same device"


# ============================================================================
# PHASE 6: CONFIG SENSORS - BASE_PATH SENSOR
# ============================================================================


async def test_base_path_config_sensor(hass: HomeAssistant, init_integration):
    """Test base_path sensor exists and has correct value."""
    state = hass.states.get("sensor.test_cleanup_base_path")
    assert state is not None, "base_path CONFIG sensor should exist"
    assert state.state == "/media/test", "Should display base_path from config"


async def test_base_path_sensor_category_config(hass: HomeAssistant, init_integration):
    """Test base_path sensor has EntityCategory.DIAGNOSTIC."""
    registry = er.async_get(hass)

    entry = registry.async_get("sensor.test_cleanup_base_path")
    assert entry is not None, "base_path sensor should exist in registry"
    assert (
        entry.entity_category == EntityCategory.DIAGNOSTIC
    ), "Should have DIAGNOSTIC category"


async def test_base_path_sensor_unique_id(hass: HomeAssistant, init_integration):
    """Test base_path sensor has correct unique_id format."""
    registry = er.async_get(hass)

    entry = registry.async_get("sensor.test_cleanup_base_path")
    assert entry is not None, "base_path sensor should exist in registry"
    assert (
        entry.unique_id == f"{init_integration.entry_id}_base_path"
    ), "Should have correct unique_id format"


async def test_base_path_sensor_linked_to_device(hass: HomeAssistant, init_integration):
    """Test base_path sensor is linked to the correct device."""
    registry = er.async_get(hass)

    entry = registry.async_get("sensor.test_cleanup_base_path")
    assert entry is not None, "base_path sensor should exist"
    assert entry.device_id is not None, "Should be linked to device"

    try:
        device_registry = hass.helpers.device_registry.async_get()
    except TypeError:
        device_registry = hass.helpers.device_registry.async_get(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, init_integration.entry_id)}
    )
    assert device is not None, "Device should exist"
    assert entry.device_id == device.id, "Should link to same device"


async def test_base_path_sensor_updates_from_coordinator(
    hass: HomeAssistant, init_integration
):
    """Test base_path sensor always shows coordinator.base_path (from config)."""
    coordinator = init_integration.runtime_data

    # base_path sensor should always show coordinator.base_path, not from coordinator.data
    state = hass.states.get("sensor.test_cleanup_base_path")
    assert state.state == coordinator.base_path, "Should show coordinator.base_path"
    assert state.state == "/media/test", "Should match config value"

    # Even if we update coordinator.data with different base_path, sensor shows config value
    coordinator.data = {
        "base_path": "/wrong/path",  # This should be ignored
    }

    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_base_path")
    assert state.state == "/media/test", "Should still show original config value"


async def test_sensor_attributes_empty(hass: HomeAssistant, init_integration):
    """Test all sensors now have empty attributes."""
    from datetime import UTC, datetime

    coordinator = init_integration.runtime_data

    coordinator.data = {
        "total_files": 100,
        "older_than_retention": 25,
        "deleted_last_run": 10,
        "deleted_bytes_last_run": 102400,
        "last_scan": datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        "last_cleanup": datetime(2024, 1, 1, 2, 0, 0, tzinfo=UTC),
        "last_scan_duration_ms": 150,
        "last_cleanup_duration_ms": 500,
        "total_folder_size_bytes": 2097152,
        "older_than_retention_size_bytes": 1048576,
        "base_path": "/media/test",
        "pattern": "*.jpg",
        "retention_days": 7,
    }

    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    test_sensors = [
        "sensor.test_cleanup_total_files",
        "sensor.test_cleanup_older_than_retention",
        "sensor.test_cleanup_deleted_last_cleanup",
        "sensor.test_cleanup_deleted_size_last_cleanup",
        "sensor.test_cleanup_total_folder_size",
        "sensor.test_cleanup_older_than_retention_size",
        "sensor.test_cleanup_last_scan",
        "sensor.test_cleanup_last_cleanup",
        "sensor.test_cleanup_last_scan_duration",
        "sensor.test_cleanup_last_cleanup_duration",
        "sensor.test_cleanup_base_path",
    ]

    for sensor_id in test_sensors:
        state = hass.states.get(sensor_id)
        assert state is not None, f"Sensor {sensor_id} should exist"

        attrs = state.attributes
        assert (
            "base_path" not in attrs
        ), f"{sensor_id} should not have base_path attribute"
        assert "pattern" not in attrs, f"{sensor_id} should not have pattern attribute"
        assert (
            "retention_days" not in attrs
        ), f"{sensor_id} should not have retention_days attribute"


async def test_base_path_sensor_handles_missing_data(
    hass: HomeAssistant, init_integration
):
    """Test base_path sensor handles missing data gracefully."""
    coordinator = init_integration.runtime_data

    coordinator.data = {
        "total_files": 50,
    }

    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_base_path")
    assert state.state in [
        "unknown",
        "/media/test",
    ], "Should show unknown or fallback to config value"


async def test_base_path_sensor_has_correct_icon(hass: HomeAssistant, init_integration):
    """Test base_path sensor has the correct folder icon."""
    state = hass.states.get("sensor.test_cleanup_base_path")
    assert state is not None, "base_path sensor should exist"
    assert state.attributes.get("icon") == "mdi:folder", "Should have folder icon"


async def test_sensor_attributes_not_restored(hass: HomeAssistant, init_integration):
    """Test that config attributes are not restored from previous state."""
    coordinator = init_integration.runtime_data

    coordinator.data = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state is not None, "total_files sensor should exist"

    attrs = state.attributes
    assert "base_path" not in attrs, "Should not restore base_path attribute"
    assert "pattern" not in attrs, "Should not restore pattern attribute"
    assert "retention_days" not in attrs, "Should not restore retention_days attribute"


async def test_base_path_sensor_no_device_class(hass: HomeAssistant, init_integration):
    """Test base_path sensor has no device class."""
    state = hass.states.get("sensor.test_cleanup_base_path")
    assert state is not None, "base_path sensor should exist"
    assert (
        state.attributes.get("device_class") is None
    ), "CONFIG sensor should not have device class"


async def test_base_path_sensor_no_state_class(hass: HomeAssistant, init_integration):
    """Test base_path sensor has no state class."""
    state = hass.states.get("sensor.test_cleanup_base_path")
    assert state is not None, "base_path sensor should exist"
    assert (
        state.attributes.get("state_class") is None
    ), "CONFIG sensor should not have state class"
