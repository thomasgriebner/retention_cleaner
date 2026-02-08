"""Test retention_cleaner switch entities."""

from unittest.mock import patch

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.retention_cleaner.const import (
    CONF_DRY_RUN,
    CONF_REMOVE_EMPTY_FOLDERS,
    DOMAIN,
)


async def test_switch_dry_run_setup(hass: HomeAssistant, init_integration):
    """Test dry_run switch entity is created during platform setup."""
    state = hass.states.get("switch.test_cleanup_dry_run")
    assert state is not None, "dry_run switch entity should exist"


async def test_switch_remove_empty_folders_setup(hass: HomeAssistant, init_integration):
    """Test remove_empty_folders switch entity is created during platform setup."""
    state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert state is not None, "remove_empty_folders switch entity should exist"


async def test_switch_both_entities_exist(hass: HomeAssistant, init_integration):
    """Test that both switch entities are created during setup."""
    dry_run_state = hass.states.get("switch.test_cleanup_dry_run")
    remove_empty_state = hass.states.get("switch.test_cleanup_remove_empty_folders")

    assert dry_run_state is not None, "dry_run switch should exist"
    assert remove_empty_state is not None, "remove_empty_folders switch should exist"


async def test_switch_dry_run_initial_state(hass: HomeAssistant, init_integration):
    """Test initial state matches coordinator config."""
    coordinator = init_integration.runtime_data

    state = hass.states.get("switch.test_cleanup_dry_run")
    assert state is not None, "dry_run switch entity should exist"

    expected_state = "on" if coordinator.dry_run else "off"
    assert (
        state.state == expected_state
    ), f"Initial state should be '{expected_state}' matching coordinator config"


async def test_switch_remove_empty_folders_initial_state(
    hass: HomeAssistant, init_integration
):
    """Test initial state matches coordinator config."""
    coordinator = init_integration.runtime_data

    state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert state is not None, "remove_empty_folders switch entity should exist"

    expected_state = "on" if coordinator.remove_empty_folders else "off"
    assert (
        state.state == expected_state
    ), f"Initial state should be '{expected_state}' matching coordinator config"


async def test_switch_dry_run_turn_on(hass: HomeAssistant, init_integration):
    """Test turning on updates config to True."""
    coordinator = init_integration.runtime_data

    coordinator.dry_run = False

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_cleanup_dry_run"},
        blocking=True,
    )

    state = hass.states.get("switch.test_cleanup_dry_run")
    assert state is not None, "Switch entity should still exist"
    assert state.state == "on", "State should be on"
    assert coordinator.dry_run is True, "Coordinator dry_run should be True"


async def test_switch_dry_run_turn_off(hass: HomeAssistant, init_integration):
    """Test turning off updates config to False."""
    coordinator = init_integration.runtime_data

    coordinator.dry_run = True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_cleanup_dry_run"},
        blocking=True,
    )

    state = hass.states.get("switch.test_cleanup_dry_run")
    assert state is not None, "Switch entity should still exist"
    assert state.state == "off", "State should be off"
    assert coordinator.dry_run is False, "Coordinator dry_run should be False"


async def test_switch_remove_empty_folders_turn_on(
    hass: HomeAssistant, init_integration
):
    """Test turning on updates config to True."""
    coordinator = init_integration.runtime_data

    coordinator.remove_empty_folders = False

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_cleanup_remove_empty_folders"},
        blocking=True,
    )

    state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert state is not None, "Switch entity should still exist"
    assert state.state == "on", "State should be on"
    assert (
        coordinator.remove_empty_folders is True
    ), "Coordinator remove_empty_folders should be True"


async def test_switch_remove_empty_folders_turn_off(
    hass: HomeAssistant, init_integration
):
    """Test turning off updates config to False."""
    coordinator = init_integration.runtime_data

    coordinator.remove_empty_folders = True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_cleanup_remove_empty_folders"},
        blocking=True,
    )

    state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert state is not None, "Switch entity should still exist"
    assert state.state == "off", "State should be off"
    assert (
        coordinator.remove_empty_folders is False
    ), "Coordinator remove_empty_folders should be False"


async def test_switch_dry_run_persists(hass: HomeAssistant, init_integration):
    """Test config is persisted via async_update_config_value."""
    coordinator = init_integration.runtime_data

    with (
        patch.object(coordinator, "async_update_config_value") as mock_update_config,
        patch.object(hass.config_entries, "async_update_entry"),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test_cleanup_dry_run"},
            blocking=True,
        )

        mock_update_config.assert_called_once_with(CONF_DRY_RUN, False)


async def test_switch_remove_empty_folders_persists(
    hass: HomeAssistant, init_integration
):
    """Test config is persisted via async_update_config_value."""
    coordinator = init_integration.runtime_data

    with (
        patch.object(coordinator, "async_update_config_value") as mock_update_config,
        patch.object(hass.config_entries, "async_update_entry"),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test_cleanup_remove_empty_folders"},
            blocking=True,
        )

        mock_update_config.assert_called_once_with(CONF_REMOVE_EMPTY_FOLDERS, True)


async def test_switch_dry_run_boolean_type_on(hass: HomeAssistant, init_integration):
    """Test turn_on passes boolean True to coordinator."""
    coordinator = init_integration.runtime_data

    with (
        patch.object(coordinator, "async_update_config_value") as mock_update_config,
        patch.object(hass.config_entries, "async_update_entry"),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test_cleanup_dry_run"},
            blocking=True,
        )

        args = mock_update_config.call_args[0]
        assert args[0] == CONF_DRY_RUN, "Should update CONF_DRY_RUN"
        assert args[1] is True, "Should pass boolean True"
        assert isinstance(args[1], bool), "Should be boolean type, not string"


async def test_switch_dry_run_boolean_type_off(hass: HomeAssistant, init_integration):
    """Test turn_off passes boolean False to coordinator."""
    coordinator = init_integration.runtime_data

    with (
        patch.object(coordinator, "async_update_config_value") as mock_update_config,
        patch.object(hass.config_entries, "async_update_entry"),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test_cleanup_dry_run"},
            blocking=True,
        )

        args = mock_update_config.call_args[0]
        assert args[0] == CONF_DRY_RUN, "Should update CONF_DRY_RUN"
        assert args[1] is False, "Should pass boolean False"
        assert isinstance(args[1], bool), "Should be boolean type, not string"


async def test_switch_dry_run_attributes(hass: HomeAssistant, init_integration):
    """Test switch entity attributes and configuration."""
    registry = er.async_get(hass)

    entry = registry.async_get("switch.test_cleanup_dry_run")
    assert entry is not None, "Switch entity should exist in registry"
    assert (
        entry.unique_id == f"{init_integration.entry_id}_dry_run"
    ), "Should have correct unique_id format"
    assert (
        entry.entity_category == EntityCategory.CONFIG
    ), "Should have CONFIG entity category"

    state = hass.states.get("switch.test_cleanup_dry_run")
    assert state is not None, "Switch entity state should exist"
    assert state.attributes.get("icon") == "mdi:test-tube", "Should have test-tube icon"


async def test_switch_remove_empty_folders_attributes(
    hass: HomeAssistant, init_integration
):
    """Test switch entity attributes and configuration."""
    registry = er.async_get(hass)

    entry = registry.async_get("switch.test_cleanup_remove_empty_folders")
    assert entry is not None, "Switch entity should exist in registry"
    assert (
        entry.unique_id == f"{init_integration.entry_id}_remove_empty_folders"
    ), "Should have correct unique_id format"
    assert (
        entry.entity_category == EntityCategory.CONFIG
    ), "Should have CONFIG entity category"

    state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert state is not None, "Switch entity state should exist"
    assert (
        state.attributes.get("icon") == "mdi:folder-remove"
    ), "Should have folder-remove icon"


async def test_switch_dry_run_device_info(hass: HomeAssistant, init_integration):
    """Test that switch entity is linked to the correct device."""
    registry = er.async_get(hass)

    entry = registry.async_get("switch.test_cleanup_dry_run")
    assert entry is not None, "Switch entity should exist"
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


async def test_switch_remove_empty_folders_device_info(
    hass: HomeAssistant, init_integration
):
    """Test that switch entity is linked to the correct device."""
    registry = er.async_get(hass)

    entry = registry.async_get("switch.test_cleanup_remove_empty_folders")
    assert entry is not None, "Switch entity should exist"
    assert entry.device_id is not None, "Should be linked to device"

    try:
        device_registry = hass.helpers.device_registry.async_get()
    except TypeError:
        device_registry = hass.helpers.device_registry.async_get(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, init_integration.entry_id)}
    )
    assert device is not None, "Device should exist"


async def test_switch_dry_run_unique_id_stable(hass: HomeAssistant, init_integration):
    """Test that switch entity unique ID remains stable."""
    registry = er.async_get(hass)
    entry_id = init_integration.entry_id

    entity_id = registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, f"{entry_id}_dry_run"
    )
    assert entity_id is not None, "Switch entity should be found by unique_id"
    assert entity_id == "switch.test_cleanup_dry_run", "Should have correct entity_id"


async def test_switch_remove_empty_folders_unique_id_stable(
    hass: HomeAssistant, init_integration
):
    """Test that switch entity unique ID remains stable."""
    registry = er.async_get(hass)
    entry_id = init_integration.entry_id

    entity_id = registry.async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, f"{entry_id}_remove_empty_folders"
    )
    assert entity_id is not None, "Switch entity should be found by unique_id"
    assert (
        entity_id == "switch.test_cleanup_remove_empty_folders"
    ), "Should have correct entity_id"


async def test_switch_dry_run_updates_from_coordinator(
    hass: HomeAssistant, init_integration
):
    """Test that switch entity reflects coordinator config changes."""
    coordinator = init_integration.runtime_data

    await coordinator.async_update_config_value(CONF_DRY_RUN, False)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_cleanup_dry_run")
    assert state is not None, "Switch entity should still exist"
    assert (
        state.state == "off"
    ), "State should reflect updated coordinator config (False -> off)"

    await coordinator.async_update_config_value(CONF_DRY_RUN, True)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_cleanup_dry_run")
    assert state is not None, "Switch entity should still exist"
    assert (
        state.state == "on"
    ), "State should reflect updated coordinator config (True -> on)"


async def test_switch_remove_empty_folders_updates_from_coordinator(
    hass: HomeAssistant, init_integration
):
    """Test that switch entity reflects coordinator config changes."""
    coordinator = init_integration.runtime_data

    await coordinator.async_update_config_value(CONF_REMOVE_EMPTY_FOLDERS, True)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert state is not None, "Switch entity should still exist"
    assert (
        state.state == "on"
    ), "State should reflect updated coordinator config (True -> on)"

    await coordinator.async_update_config_value(CONF_REMOVE_EMPTY_FOLDERS, False)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert state is not None, "Switch entity should still exist"
    assert (
        state.state == "off"
    ), "State should reflect updated coordinator config (False -> off)"


@pytest.mark.parametrize(
    ("initial_value", "service", "expected_bool", "expected_state"),
    [
        (True, SERVICE_TURN_OFF, False, "off"),
        (False, SERVICE_TURN_ON, True, "on"),
        (True, SERVICE_TURN_ON, True, "on"),
        (False, SERVICE_TURN_OFF, False, "off"),
    ],
)
async def test_switch_dry_run_multiple_toggles(
    hass: HomeAssistant,
    init_integration,
    initial_value,
    service,
    expected_bool,
    expected_state,
):
    """Test multiple switch toggles work correctly."""
    coordinator = init_integration.runtime_data

    coordinator.dry_run = initial_value

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "switch.test_cleanup_dry_run"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_cleanup_dry_run")
    assert state.state == expected_state, f"Should update to {expected_state}"
    assert (
        coordinator.dry_run == expected_bool
    ), f"Coordinator should have {expected_bool}"


@pytest.mark.parametrize(
    ("initial_value", "service", "expected_bool", "expected_state"),
    [
        (True, SERVICE_TURN_OFF, False, "off"),
        (False, SERVICE_TURN_ON, True, "on"),
        (True, SERVICE_TURN_ON, True, "on"),
        (False, SERVICE_TURN_OFF, False, "off"),
    ],
)
async def test_switch_remove_empty_folders_multiple_toggles(
    hass: HomeAssistant,
    init_integration,
    initial_value,
    service,
    expected_bool,
    expected_state,
):
    """Test multiple switch toggles work correctly."""
    coordinator = init_integration.runtime_data

    coordinator.remove_empty_folders = initial_value

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "switch.test_cleanup_remove_empty_folders"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert state.state == expected_state, f"Should update to {expected_state}"
    assert (
        coordinator.remove_empty_folders == expected_bool
    ), f"Coordinator should have {expected_bool}"


async def test_switch_dry_run_initial_state_true(hass: HomeAssistant):
    """Test initial state displays on when coordinator has dry_run=True."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry_true = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Dry Run True",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
            "dry_run": True,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_dry_run_true_entry",
    )
    entry_true.add_to_hass(hass)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
    ):
        assert await hass.config_entries.async_setup(entry_true.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("switch.test_dry_run_true_dry_run")
    assert state is not None, "Switch entity should exist"
    assert state.state == "on", "Should display on when dry_run is True"


async def test_switch_dry_run_initial_state_false(hass: HomeAssistant):
    """Test initial state displays off when coordinator has dry_run=False."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry_false = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Dry Run False",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
            "dry_run": False,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_dry_run_false_entry",
    )
    entry_false.add_to_hass(hass)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
    ):
        assert await hass.config_entries.async_setup(entry_false.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("switch.test_dry_run_false_dry_run")
    assert state is not None, "Switch entity should exist"
    assert state.state == "off", "Should display off when dry_run is False"


async def test_switch_remove_empty_folders_initial_state_true(hass: HomeAssistant):
    """Test initial state displays on when coordinator has remove_empty_folders=True."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry_true = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Remove Empty True",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
            "dry_run": False,
            "max_deletes": 100,
            "run_at": "02:00",
            "remove_empty_folders": True,
        },
        entry_id="test_remove_empty_true_entry",
    )
    entry_true.add_to_hass(hass)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
    ):
        assert await hass.config_entries.async_setup(entry_true.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("switch.test_remove_empty_true_remove_empty_folders")
    assert state is not None, "Switch entity should exist"
    assert state.state == "on", "Should display on when remove_empty_folders is True"


async def test_switch_remove_empty_folders_initial_state_false(hass: HomeAssistant):
    """Test initial state displays off when coordinator has remove_empty_folders=False."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry_false = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Remove Empty False",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
            "dry_run": False,
            "max_deletes": 100,
            "run_at": "02:00",
            "remove_empty_folders": False,
        },
        entry_id="test_remove_empty_false_entry",
    )
    entry_false.add_to_hass(hass)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
    ):
        assert await hass.config_entries.async_setup(entry_false.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("switch.test_remove_empty_false_remove_empty_folders")
    assert state is not None, "Switch entity should exist"
    assert state.state == "off", "Should display off when remove_empty_folders is False"


async def test_switch_dry_run_availability(hass: HomeAssistant, init_integration):
    """Test switch entity availability based on coordinator."""
    coordinator = init_integration.runtime_data

    state = hass.states.get("switch.test_cleanup_dry_run")
    assert state.state != "unavailable", "Should be available when coordinator is ready"

    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_cleanup_dry_run")
    assert (
        state.state != "unavailable"
    ), "Switch entity should remain available even with no coordinator data"


async def test_switch_remove_empty_folders_availability(
    hass: HomeAssistant, init_integration
):
    """Test switch entity availability based on coordinator."""
    coordinator = init_integration.runtime_data

    state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert state.state != "unavailable", "Should be available when coordinator is ready"

    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert (
        state.state != "unavailable"
    ), "Switch entity should remain available even with no coordinator data"


async def test_switch_dry_run_updates_trigger_no_scan(
    hass: HomeAssistant, init_integration
):
    """Test that switch updates do not trigger coordinator refresh."""
    coordinator = init_integration.runtime_data

    initial_last_scan = coordinator.last_scan

    with patch.object(hass.config_entries, "async_update_entry"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test_cleanup_dry_run"},
            blocking=True,
        )

    assert (
        coordinator.last_scan == initial_last_scan
    ), "Coordinator should not have refreshed for dry_run change"


async def test_switch_remove_empty_folders_updates_trigger_no_scan(
    hass: HomeAssistant, init_integration
):
    """Test that switch updates do not trigger coordinator refresh."""
    coordinator = init_integration.runtime_data

    initial_last_scan = coordinator.last_scan

    with patch.object(hass.config_entries, "async_update_entry"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test_cleanup_remove_empty_folders"},
            blocking=True,
        )

    assert (
        coordinator.last_scan == initial_last_scan
    ), "Coordinator should not have refreshed for remove_empty_folders change"


async def test_switch_dry_run_round_trip_boolean(hass: HomeAssistant, init_integration):
    """Test boolean round trip: True -> on display, turn_on -> True storage."""
    coordinator = init_integration.runtime_data

    coordinator.dry_run = True
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_cleanup_dry_run")
    assert state.state == "on", "True should display as on"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_cleanup_dry_run"},
        blocking=True,
    )

    assert coordinator.dry_run is True, "turn_on should store as True boolean"
    assert isinstance(coordinator.dry_run, bool), "Should remain boolean type"


async def test_switch_remove_empty_folders_round_trip_boolean(
    hass: HomeAssistant, init_integration
):
    """Test boolean round trip: False -> off display, turn_off -> False storage."""
    coordinator = init_integration.runtime_data

    coordinator.remove_empty_folders = False
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert state.state == "off", "False should display as off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_cleanup_remove_empty_folders"},
        blocking=True,
    )

    assert (
        coordinator.remove_empty_folders is False
    ), "turn_off should store as False boolean"
    assert isinstance(
        coordinator.remove_empty_folders, bool
    ), "Should remain boolean type"


async def test_switch_dry_run_friendly_name(hass: HomeAssistant, init_integration):
    """Test switch entity has correct friendly name."""
    state = hass.states.get("switch.test_cleanup_dry_run")
    assert state is not None, "Switch entity should exist"
    assert (
        state.attributes.get("friendly_name") == "Test Cleanup Dry run"
    ), "Should have correct friendly name"


async def test_switch_remove_empty_folders_friendly_name(
    hass: HomeAssistant, init_integration
):
    """Test switch entity has correct friendly name."""
    state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert state is not None, "Switch entity should exist"
    assert (
        state.attributes.get("friendly_name")
        == "Test Cleanup Remove empty folders after cleanup"
    ), "Should have correct friendly name"


async def test_switch_dry_run_no_options_attribute(
    hass: HomeAssistant, init_integration
):
    """Test switch entity does not have options attribute."""
    state = hass.states.get("switch.test_cleanup_dry_run")
    assert state is not None, "Switch entity should exist"
    assert "options" not in state.attributes, "Switch should not have options attribute"


async def test_switch_remove_empty_folders_no_options_attribute(
    hass: HomeAssistant, init_integration
):
    """Test switch entity does not have options attribute."""
    state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert state is not None, "Switch entity should exist"
    assert "options" not in state.attributes, "Switch should not have options attribute"
