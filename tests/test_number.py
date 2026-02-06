"""Test retention_cleaner number entities."""

from unittest.mock import patch

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.retention_cleaner.const import (
    CONF_KEEP_MINIMUM_FILES,
    CONF_MAX_DELETES,
    CONF_MAX_FILES_IN_FOLDER,
    CONF_RETENTION_DAYS,
    DOMAIN,
)


async def test_number_entity_setup(hass: HomeAssistant, init_integration):
    """Test number entity is created during platform setup."""
    state = hass.states.get("number.test_cleanup_retention_days")
    assert state is not None, "retention_days number entity should exist"


async def test_number_entity_initial_value(hass: HomeAssistant, init_integration):
    """Test initial value matches coordinator config."""
    coordinator = init_integration.runtime_data

    state = hass.states.get("number.test_cleanup_retention_days")
    assert state is not None, "retention_days number entity should exist"
    assert (
        float(state.state) == coordinator.retention_days
    ), "Initial value should match coordinator config"


async def test_number_entity_set_value(hass: HomeAssistant, init_integration):
    """Test setting value updates the entity state."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_cleanup_retention_days", ATTR_VALUE: 14},
        blocking=True,
    )

    state = hass.states.get("number.test_cleanup_retention_days")
    assert state is not None, "Number entity should still exist"
    assert float(state.state) == 14, "State should be updated to new value"


async def test_number_entity_set_value_updates_config(
    hass: HomeAssistant, init_integration
):
    """Test config is persisted via async_update_config_value."""
    coordinator = init_integration.runtime_data

    with (
        patch.object(coordinator, "async_update_config_value") as mock_update_config,
        patch.object(hass.config_entries, "async_update_entry"),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.test_cleanup_retention_days", ATTR_VALUE: 21},
            blocking=True,
        )

        mock_update_config.assert_called_once_with(CONF_RETENTION_DAYS, 21)


async def test_number_entity_set_value_triggers_scan(
    hass: HomeAssistant, init_integration
):
    """Test coordinator refresh is triggered."""
    coordinator = init_integration.runtime_data

    initial_last_scan = coordinator.last_scan

    with patch.object(hass.config_entries, "async_update_entry"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.test_cleanup_retention_days", ATTR_VALUE: 30},
            blocking=True,
        )

    assert (
        coordinator.last_scan != initial_last_scan
    ), "Coordinator should have refreshed"


async def test_number_entity_min_max_validation(hass: HomeAssistant, init_integration):
    """Test min (1) and max (3650) boundaries are respected."""
    registry = er.async_get(hass)

    entry = registry.async_get("number.test_cleanup_retention_days")
    assert entry is not None, "Number entity should exist in registry"

    state = hass.states.get("number.test_cleanup_retention_days")
    assert state is not None, "Number entity state should exist"

    assert state.attributes.get("min") == 1, "Min value should be 1"
    assert state.attributes.get("max") == 3650, "Max value should be 3650"
    assert state.attributes.get("step") == 1, "Step value should be 1"


async def test_number_entity_attributes(hass: HomeAssistant, init_integration):
    """Test number entity attributes and configuration."""
    registry = er.async_get(hass)

    entry = registry.async_get("number.test_cleanup_retention_days")
    assert entry is not None, "Number entity should exist in registry"
    assert (
        entry.unique_id == f"{init_integration.entry_id}_retention_days"
    ), "Should have correct unique_id format"
    assert (
        entry.entity_category == EntityCategory.CONFIG
    ), "Should have CONFIG entity category"

    state = hass.states.get("number.test_cleanup_retention_days")
    assert state is not None, "Number entity state should exist"
    assert (
        state.attributes.get("unit_of_measurement") == "days"
    ), "Should have 'days' unit"
    assert (
        state.attributes.get("mode") == "box"
    ), "Should have 'box' mode for text input"


async def test_number_entity_device_info(hass: HomeAssistant, init_integration):
    """Test that number entity is linked to the correct device."""
    registry = er.async_get(hass)

    entry = registry.async_get("number.test_cleanup_retention_days")
    assert entry is not None, "Number entity should exist"
    assert entry.device_id is not None, "Should be linked to device"

    try:
        device_registry = hass.helpers.device_registry.async_get()
    except TypeError:
        device_registry = hass.helpers.device_registry.async_get(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, init_integration.entry_id)}
    )
    assert device is not None, "Device should exist"
    assert device.name == "Test Cleanup", "Device should have correct name"
    assert device.model == "Folder retention rule", "Device should have correct model"
    assert (
        device.manufacturer == "Retention Cleaner"
    ), "Device should have correct manufacturer"
    assert (
        DOMAIN,
        init_integration.entry_id,
    ) in device.identifiers, "Device should have correct identifiers"


async def test_number_entity_unique_id_stable(hass: HomeAssistant, init_integration):
    """Test that number entity unique ID remains stable."""
    registry = er.async_get(hass)
    entry_id = init_integration.entry_id

    entity_id = registry.async_get_entity_id(
        NUMBER_DOMAIN, DOMAIN, f"{entry_id}_retention_days"
    )
    assert entity_id is not None, "Number entity should be found by unique_id"
    assert (
        entity_id == "number.test_cleanup_retention_days"
    ), "Should have correct entity_id"


async def test_number_entity_updates_from_coordinator(
    hass: HomeAssistant, init_integration
):
    """Test that number entity reflects coordinator config changes."""
    coordinator = init_integration.runtime_data

    await coordinator.async_update_config_value(CONF_RETENTION_DAYS, 45)
    await hass.async_block_till_done()

    state = hass.states.get("number.test_cleanup_retention_days")
    assert state is not None, "Number entity should still exist"
    assert float(state.state) == 45, "State should reflect updated coordinator config"


async def test_number_entity_boundary_values(hass: HomeAssistant):
    """Test setting boundary values (min=1, max=3650)."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry_min = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Min Retention",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 1,
            "dry_run": True,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_min_entry",
    )
    entry_min.add_to_hass(hass)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
    ):
        assert await hass.config_entries.async_setup(entry_min.entry_id)
        await hass.async_block_till_done()

    state_min = hass.states.get("number.test_min_retention_retention_days")
    assert float(state_min.state) == 1, "Should accept minimum value of 1"

    entry_max = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Max Retention",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 3650,
            "dry_run": True,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_max_entry",
    )
    entry_max.add_to_hass(hass)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
    ):
        assert await hass.config_entries.async_setup(entry_max.entry_id)
        await hass.async_block_till_done()

    state_max = hass.states.get("number.test_max_retention_retention_days")
    assert float(state_max.state) == 3650, "Should accept maximum value of 3650"


async def test_number_entity_multiple_updates(hass: HomeAssistant, init_integration):
    """Test multiple value updates work correctly."""
    coordinator = init_integration.runtime_data

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.test_cleanup_retention_days",
            ATTR_VALUE: 30,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("number.test_cleanup_retention_days")
    assert float(state.state) == 30, "Should update to 30 days"
    assert coordinator.retention_days == 30, "Coordinator should have 30 days"


async def test_number_entity_availability(hass: HomeAssistant, init_integration):
    """Test number entity availability based on coordinator."""
    coordinator = init_integration.runtime_data

    state = hass.states.get("number.test_cleanup_retention_days")
    assert state.state != "unavailable", "Should be available when coordinator is ready"

    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    state = hass.states.get("number.test_cleanup_retention_days")
    assert (
        state.state != "unavailable"
    ), "Number entity should remain available even with no coordinator data"


# ==================== MAX_DELETES NUMBER ENTITY TESTS ====================


async def test_number_max_deletes_setup(hass: HomeAssistant, init_integration):
    """Test max_deletes number entity is created during platform setup."""
    state = hass.states.get("number.test_cleanup_max_deletes")
    assert state is not None, "max_deletes number entity should exist"


async def test_number_max_deletes_initial_value(hass: HomeAssistant, init_integration):
    """Test initial value matches coordinator config."""
    coordinator = init_integration.runtime_data

    state = hass.states.get("number.test_cleanup_max_deletes")
    assert state is not None, "max_deletes entity should exist"

    assert (
        float(state.state) == coordinator.max_deletes
    ), "Initial value should match coordinator"


async def test_number_max_deletes_set_value(hass: HomeAssistant, init_integration):
    """Test setting value via number.set_value service."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.test_cleanup_max_deletes",
            ATTR_VALUE: 500,
        },
        blocking=True,
    )

    state = hass.states.get("number.test_cleanup_max_deletes")
    assert state is not None, "Entity should still exist after update"
    assert float(state.state) == 500, "State should be updated to 500"


async def test_number_max_deletes_set_value_updates_config(
    hass: HomeAssistant, init_integration
):
    """Test config is persisted via async_update_config_value."""
    coordinator = init_integration.runtime_data

    with (
        patch.object(coordinator, "async_update_config_value") as mock_update_config,
        patch.object(hass.config_entries, "async_update_entry"),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.test_cleanup_max_deletes", ATTR_VALUE: 2000},
            blocking=True,
        )

        mock_update_config.assert_called_once_with(CONF_MAX_DELETES, 2000)


async def test_number_max_deletes_set_value_triggers_scan(
    hass: HomeAssistant, init_integration
):
    """Test coordinator refresh is triggered."""
    coordinator = init_integration.runtime_data

    initial_last_scan = coordinator.last_scan

    with patch.object(hass.config_entries, "async_update_entry"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.test_cleanup_max_deletes", ATTR_VALUE: 3000},
            blocking=True,
        )

    assert (
        coordinator.last_scan != initial_last_scan
    ), "Coordinator should have refreshed"


async def test_number_max_deletes_min_max_validation(
    hass: HomeAssistant, init_integration
):
    """Test min (1) and max (10000) boundaries are enforced."""
    registry = er.async_get(hass)

    entry = registry.async_get("number.test_cleanup_max_deletes")
    assert entry is not None, "max_deletes entity should exist in registry"

    state = hass.states.get("number.test_cleanup_max_deletes")
    assert state is not None, "max_deletes entity state should exist"

    assert state.attributes.get("min") == 1, "Min value should be 1"
    assert state.attributes.get("max") == 10000, "Max value should be 10000"
    assert state.attributes.get("step") == 1, "Step value should be 1"


async def test_number_max_deletes_attributes(hass: HomeAssistant, init_integration):
    """Test max_deletes entity attributes and configuration."""
    registry = er.async_get(hass)

    entry = registry.async_get("number.test_cleanup_max_deletes")
    assert entry is not None, "max_deletes entity should exist in registry"
    assert (
        entry.unique_id == f"{init_integration.entry_id}_max_deletes"
    ), "Should have correct unique_id format"
    assert (
        entry.entity_category == EntityCategory.CONFIG
    ), "Should have CONFIG entity category"

    state = hass.states.get("number.test_cleanup_max_deletes")
    assert state is not None, "max_deletes entity state should exist"
    assert (
        state.attributes.get("unit_of_measurement") == "files"
    ), "Should have 'files' unit"
    assert (
        state.attributes.get("mode") == "box"
    ), "Should have 'box' mode for text input"


async def test_number_max_deletes_device_info(hass: HomeAssistant, init_integration):
    """Test that max_deletes entity is linked to the correct device."""
    registry = er.async_get(hass)

    entry = registry.async_get("number.test_cleanup_max_deletes")
    assert entry is not None, "max_deletes entity should exist"
    assert entry.device_id is not None, "Should be linked to device"

    try:
        device_registry = hass.helpers.device_registry.async_get()
    except TypeError:
        device_registry = hass.helpers.device_registry.async_get(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, init_integration.entry_id)}
    )
    assert device is not None, "Device should exist"
    assert (
        DOMAIN,
        init_integration.entry_id,
    ) in device.identifiers, "Device should have correct identifiers"


async def test_number_max_deletes_unique_id_stable(
    hass: HomeAssistant, init_integration
):
    """Test that max_deletes entity unique ID remains stable."""
    registry = er.async_get(hass)
    entry_id = init_integration.entry_id

    entity_id = registry.async_get_entity_id(
        NUMBER_DOMAIN, DOMAIN, f"{entry_id}_max_deletes"
    )
    assert entity_id is not None, "max_deletes entity should be found by unique_id"
    assert (
        entity_id == "number.test_cleanup_max_deletes"
    ), "Should have correct entity_id"


async def test_number_max_deletes_updates_from_coordinator(
    hass: HomeAssistant, init_integration
):
    """Test that max_deletes entity reflects coordinator config changes."""
    coordinator = init_integration.runtime_data

    await coordinator.async_update_config_value(CONF_MAX_DELETES, 7500)
    await hass.async_block_till_done()

    state = hass.states.get("number.test_cleanup_max_deletes")
    assert state is not None, "max_deletes entity should still exist"
    assert float(state.state) == 7500, "State should reflect updated coordinator config"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, 1),
        (10000, 10000),
        (1000, 1000),
        (5000, 5000),
    ],
)
async def test_number_max_deletes_boundary_values(
    hass: HomeAssistant, init_integration, value, expected
):
    """Test boundary values are accepted."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_cleanup_max_deletes", ATTR_VALUE: value},
        blocking=True,
    )

    state = hass.states.get("number.test_cleanup_max_deletes")
    assert float(state.state) == expected, f"Should accept value {expected}"


# ==================== KEEP_MINIMUM_FILES NUMBER ENTITY TESTS ====================


async def test_number_keep_minimum_files_setup(hass: HomeAssistant, init_integration):
    """Test keep_minimum_files number entity is created during platform setup."""
    state = hass.states.get("number.test_cleanup_keep_minimum_files")
    assert state is not None, "keep_minimum_files number entity should exist"


async def test_number_keep_minimum_files_initial_value(
    hass: HomeAssistant, init_integration
):
    """Test initial value matches coordinator config."""
    coordinator = init_integration.runtime_data

    state = hass.states.get("number.test_cleanup_keep_minimum_files")
    assert state is not None, "keep_minimum_files entity should exist"

    assert (
        float(state.state) == coordinator.keep_minimum_files
    ), "Initial value should match coordinator"


async def test_number_keep_minimum_files_set_value(
    hass: HomeAssistant, init_integration
):
    """Test setting value via number.set_value service."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.test_cleanup_keep_minimum_files",
            ATTR_VALUE: 100,
        },
        blocking=True,
    )

    state = hass.states.get("number.test_cleanup_keep_minimum_files")
    assert state is not None, "Entity should still exist after update"
    assert float(state.state) == 100, "State should be updated to 100"


async def test_number_keep_minimum_files_set_value_updates_config(
    hass: HomeAssistant, init_integration
):
    """Test config is persisted via async_update_config_value."""
    coordinator = init_integration.runtime_data

    with (
        patch.object(coordinator, "async_update_config_value") as mock_update_config,
        patch.object(hass.config_entries, "async_update_entry"),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.test_cleanup_keep_minimum_files", ATTR_VALUE: 250},
            blocking=True,
        )

        mock_update_config.assert_called_once_with(CONF_KEEP_MINIMUM_FILES, 250)


async def test_number_keep_minimum_files_set_value_triggers_scan(
    hass: HomeAssistant, init_integration
):
    """Test coordinator refresh is triggered."""
    coordinator = init_integration.runtime_data

    initial_last_scan = coordinator.last_scan

    with patch.object(hass.config_entries, "async_update_entry"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.test_cleanup_keep_minimum_files", ATTR_VALUE: 500},
            blocking=True,
        )

    assert (
        coordinator.last_scan != initial_last_scan
    ), "Coordinator should have refreshed"


async def test_number_keep_minimum_files_min_max_validation(
    hass: HomeAssistant, init_integration
):
    """Test min (0) and max (10000) boundaries are enforced."""
    registry = er.async_get(hass)

    entry = registry.async_get("number.test_cleanup_keep_minimum_files")
    assert entry is not None, "keep_minimum_files entity should exist in registry"

    state = hass.states.get("number.test_cleanup_keep_minimum_files")
    assert state is not None, "keep_minimum_files entity state should exist"

    assert state.attributes.get("min") == 0, "Min value should be 0"
    assert state.attributes.get("max") == 10000, "Max value should be 10000"
    assert state.attributes.get("step") == 1, "Step value should be 1"


async def test_number_keep_minimum_files_attributes(
    hass: HomeAssistant, init_integration
):
    """Test keep_minimum_files entity attributes and configuration."""
    registry = er.async_get(hass)

    entry = registry.async_get("number.test_cleanup_keep_minimum_files")
    assert entry is not None, "keep_minimum_files entity should exist in registry"
    assert (
        entry.unique_id == f"{init_integration.entry_id}_keep_minimum_files"
    ), "Should have correct unique_id format"
    assert (
        entry.entity_category == EntityCategory.CONFIG
    ), "Should have CONFIG entity category"

    state = hass.states.get("number.test_cleanup_keep_minimum_files")
    assert state is not None, "keep_minimum_files entity state should exist"
    assert (
        state.attributes.get("unit_of_measurement") == "files"
    ), "Should have 'files' unit"
    assert (
        state.attributes.get("mode") == "box"
    ), "Should have 'box' mode for text input"


async def test_number_keep_minimum_files_device_info(
    hass: HomeAssistant, init_integration
):
    """Test that keep_minimum_files entity is linked to the correct device."""
    registry = er.async_get(hass)

    entry = registry.async_get("number.test_cleanup_keep_minimum_files")
    assert entry is not None, "keep_minimum_files entity should exist"
    assert entry.device_id is not None, "Should be linked to device"

    try:
        device_registry = hass.helpers.device_registry.async_get()
    except TypeError:
        device_registry = hass.helpers.device_registry.async_get(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, init_integration.entry_id)}
    )
    assert device is not None, "Device should exist"
    assert (
        DOMAIN,
        init_integration.entry_id,
    ) in device.identifiers, "Device should have correct identifiers"


async def test_number_keep_minimum_files_unique_id_stable(
    hass: HomeAssistant, init_integration
):
    """Test that keep_minimum_files entity unique ID remains stable."""
    registry = er.async_get(hass)
    entry_id = init_integration.entry_id

    entity_id = registry.async_get_entity_id(
        NUMBER_DOMAIN, DOMAIN, f"{entry_id}_keep_minimum_files"
    )
    assert (
        entity_id is not None
    ), "keep_minimum_files entity should be found by unique_id"
    assert (
        entity_id == "number.test_cleanup_keep_minimum_files"
    ), "Should have correct entity_id"


async def test_number_keep_minimum_files_updates_from_coordinator(
    hass: HomeAssistant, init_integration
):
    """Test that keep_minimum_files entity reflects coordinator config changes."""
    coordinator = init_integration.runtime_data

    await coordinator.async_update_config_value(CONF_KEEP_MINIMUM_FILES, 1000)
    await hass.async_block_till_done()

    state = hass.states.get("number.test_cleanup_keep_minimum_files")
    assert state is not None, "keep_minimum_files entity should still exist"
    assert float(state.state) == 1000, "State should reflect updated coordinator config"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0),
        (10000, 10000),
        (100, 100),
        (5000, 5000),
    ],
)
async def test_number_keep_minimum_files_boundary_values(
    hass: HomeAssistant, init_integration, value, expected
):
    """Test boundary values are accepted."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_cleanup_keep_minimum_files", ATTR_VALUE: value},
        blocking=True,
    )

    state = hass.states.get("number.test_cleanup_keep_minimum_files")
    assert float(state.state) == expected, f"Should accept value {expected}"


# ==================== MAX_FILES_IN_FOLDER NUMBER ENTITY TESTS ====================


async def test_number_max_files_in_folder_setup(hass: HomeAssistant, init_integration):
    """Test max_files_in_folder number entity is created during platform setup."""
    state = hass.states.get("number.test_cleanup_max_files_in_folder")
    assert state is not None, "max_files_in_folder number entity should exist"


async def test_number_max_files_in_folder_initial_value(
    hass: HomeAssistant, init_integration
):
    """Test initial value matches coordinator config."""
    coordinator = init_integration.runtime_data

    state = hass.states.get("number.test_cleanup_max_files_in_folder")
    assert state is not None, "max_files_in_folder entity should exist"

    assert (
        float(state.state) == coordinator.max_files_in_folder
    ), "Initial value should match coordinator"


async def test_number_max_files_in_folder_set_value(
    hass: HomeAssistant, init_integration
):
    """Test setting value via number.set_value service."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.test_cleanup_max_files_in_folder",
            ATTR_VALUE: 50000,
        },
        blocking=True,
    )

    state = hass.states.get("number.test_cleanup_max_files_in_folder")
    assert state is not None, "Entity should still exist after update"
    assert float(state.state) == 50000, "State should be updated to 50000"


async def test_number_max_files_in_folder_set_value_updates_config(
    hass: HomeAssistant, init_integration
):
    """Test config is persisted via async_update_config_value."""
    coordinator = init_integration.runtime_data

    with (
        patch.object(coordinator, "async_update_config_value") as mock_update_config,
        patch.object(hass.config_entries, "async_update_entry"),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.test_cleanup_max_files_in_folder",
                ATTR_VALUE: 100000,
            },
            blocking=True,
        )

        mock_update_config.assert_called_once_with(CONF_MAX_FILES_IN_FOLDER, 100000)


async def test_number_max_files_in_folder_set_value_triggers_scan(
    hass: HomeAssistant, init_integration
):
    """Test coordinator refresh is triggered."""
    coordinator = init_integration.runtime_data

    initial_last_scan = coordinator.last_scan

    with patch.object(hass.config_entries, "async_update_entry"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.test_cleanup_max_files_in_folder",
                ATTR_VALUE: 75000,
            },
            blocking=True,
        )

    assert (
        coordinator.last_scan != initial_last_scan
    ), "Coordinator should have refreshed"


async def test_number_max_files_in_folder_min_max_validation(
    hass: HomeAssistant, init_integration
):
    """Test min (0) and max (1000000) boundaries are enforced."""
    registry = er.async_get(hass)

    entry = registry.async_get("number.test_cleanup_max_files_in_folder")
    assert entry is not None, "max_files_in_folder entity should exist in registry"

    state = hass.states.get("number.test_cleanup_max_files_in_folder")
    assert state is not None, "max_files_in_folder entity state should exist"

    assert state.attributes.get("min") == 0, "Min value should be 0"
    assert state.attributes.get("max") == 1000000, "Max value should be 1000000"
    assert state.attributes.get("step") == 1, "Step value should be 1"


async def test_number_max_files_in_folder_attributes(
    hass: HomeAssistant, init_integration
):
    """Test max_files_in_folder entity attributes and configuration."""
    registry = er.async_get(hass)

    entry = registry.async_get("number.test_cleanup_max_files_in_folder")
    assert entry is not None, "max_files_in_folder entity should exist in registry"
    assert (
        entry.unique_id == f"{init_integration.entry_id}_max_files_in_folder"
    ), "Should have correct unique_id format"
    assert (
        entry.entity_category == EntityCategory.CONFIG
    ), "Should have CONFIG entity category"

    state = hass.states.get("number.test_cleanup_max_files_in_folder")
    assert state is not None, "max_files_in_folder entity state should exist"
    assert (
        state.attributes.get("unit_of_measurement") == "files"
    ), "Should have 'files' unit"
    assert (
        state.attributes.get("mode") == "box"
    ), "Should have 'box' mode for text input"


async def test_number_max_files_in_folder_device_info(
    hass: HomeAssistant, init_integration
):
    """Test that max_files_in_folder entity is linked to the correct device."""
    registry = er.async_get(hass)

    entry = registry.async_get("number.test_cleanup_max_files_in_folder")
    assert entry is not None, "max_files_in_folder entity should exist"
    assert entry.device_id is not None, "Should be linked to device"

    try:
        device_registry = hass.helpers.device_registry.async_get()
    except TypeError:
        device_registry = hass.helpers.device_registry.async_get(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, init_integration.entry_id)}
    )
    assert device is not None, "Device should exist"
    assert (
        DOMAIN,
        init_integration.entry_id,
    ) in device.identifiers, "Device should have correct identifiers"


async def test_number_max_files_in_folder_unique_id_stable(
    hass: HomeAssistant, init_integration
):
    """Test that max_files_in_folder entity unique ID remains stable."""
    registry = er.async_get(hass)
    entry_id = init_integration.entry_id

    entity_id = registry.async_get_entity_id(
        NUMBER_DOMAIN, DOMAIN, f"{entry_id}_max_files_in_folder"
    )
    assert (
        entity_id is not None
    ), "max_files_in_folder entity should be found by unique_id"
    assert (
        entity_id == "number.test_cleanup_max_files_in_folder"
    ), "Should have correct entity_id"


async def test_number_max_files_in_folder_updates_from_coordinator(
    hass: HomeAssistant, init_integration
):
    """Test that max_files_in_folder entity reflects coordinator config changes."""
    coordinator = init_integration.runtime_data

    await coordinator.async_update_config_value(CONF_MAX_FILES_IN_FOLDER, 250000)
    await hass.async_block_till_done()

    state = hass.states.get("number.test_cleanup_max_files_in_folder")
    assert state is not None, "max_files_in_folder entity should still exist"
    assert (
        float(state.state) == 250000
    ), "State should reflect updated coordinator config"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0),
        (1000000, 1000000),
        (10000, 10000),
        (500000, 500000),
    ],
)
async def test_number_max_files_in_folder_boundary_values(
    hass: HomeAssistant, init_integration, value, expected
):
    """Test boundary values are accepted."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_cleanup_max_files_in_folder", ATTR_VALUE: value},
        blocking=True,
    )

    state = hass.states.get("number.test_cleanup_max_files_in_folder")
    assert float(state.state) == expected, f"Should accept value {expected}"


async def test_number_max_files_in_folder_zero_unlimited(
    hass: HomeAssistant, init_integration
):
    """Test that 0 means unlimited."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_cleanup_max_files_in_folder", ATTR_VALUE: 0},
        blocking=True,
    )

    coordinator = init_integration.runtime_data
    state = hass.states.get("number.test_cleanup_max_files_in_folder")

    assert float(state.state) == 0, "State should be 0"
    assert (
        coordinator.max_files_in_folder == 0
    ), "Coordinator should store 0 (unlimited)"


# ==================== COMBINED TESTS FOR ALL NUMBER ENTITIES ====================


async def test_number_all_four_entities_exist(hass: HomeAssistant, init_integration):
    """Test all 4 number entities are created."""
    entities = [
        "number.test_cleanup_retention_days",
        "number.test_cleanup_max_deletes",
        "number.test_cleanup_keep_minimum_files",
        "number.test_cleanup_max_files_in_folder",
    ]

    for entity_id in entities:
        state = hass.states.get(entity_id)
        assert state is not None, f"Entity {entity_id} should exist"


async def test_number_all_have_config_category(hass: HomeAssistant, init_integration):
    """Test all number entities have CONFIG category."""
    ent_reg = er.async_get(hass)

    entities = [
        "number.test_cleanup_retention_days",
        "number.test_cleanup_max_deletes",
        "number.test_cleanup_keep_minimum_files",
        "number.test_cleanup_max_files_in_folder",
    ]

    for entity_id in entities:
        entity_entry = ent_reg.async_get(entity_id)
        assert entity_entry is not None, f"Entity {entity_id} should be registered"
        assert (
            entity_entry.entity_category == EntityCategory.CONFIG
        ), f"Entity {entity_id} should have CONFIG category"
