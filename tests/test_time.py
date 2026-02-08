"""Test retention_cleaner time entities."""

from datetime import time as dt_time
from unittest.mock import patch

from homeassistant.components.time import (
    ATTR_TIME,
    DOMAIN as TIME_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.retention_cleaner.const import CONF_RUN_AT, DOMAIN


async def test_time_entity_setup(hass: HomeAssistant, init_integration):
    """Test time entity is created during platform setup."""
    state = hass.states.get("time.test_cleanup_run_at")
    assert state is not None, "run_at time entity should exist"


async def test_time_entity_initial_value(hass: HomeAssistant, init_integration):
    """Test initial time matches coordinator config (HH:MM format)."""
    coordinator = init_integration.runtime_data

    state = hass.states.get("time.test_cleanup_run_at")
    assert state is not None, "run_at time entity should exist"

    coordinator_time = coordinator.run_at
    state_time = dt_time.fromisoformat(state.state)

    assert (
        state_time.hour == coordinator_time.hour
        and state_time.minute == coordinator_time.minute
    ), "Initial time should match coordinator config"


async def test_time_entity_set_value(hass: HomeAssistant, init_integration):
    """Test setting time updates the entity state."""
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "time.test_cleanup_run_at", ATTR_TIME: "14:30:00"},
        blocking=True,
    )

    state = hass.states.get("time.test_cleanup_run_at")
    assert state is not None, "Time entity should still exist"

    state_time = dt_time.fromisoformat(state.state)
    assert (
        state_time.hour == 14 and state_time.minute == 30
    ), "State should be updated to new time"


async def test_time_entity_set_value_updates_config(
    hass: HomeAssistant, init_integration
):
    """Test config is persisted via async_update_config_value."""
    coordinator = init_integration.runtime_data

    with (
        patch.object(coordinator, "async_update_config_value") as mock_update_config,
        patch.object(hass.config_entries, "async_update_entry"),
    ):
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "time.test_cleanup_run_at", ATTR_TIME: "04:45:00"},
            blocking=True,
        )

        mock_update_config.assert_called_once_with(CONF_RUN_AT, "04:45")


async def test_time_entity_triggers_scheduler_update(
    hass: HomeAssistant, init_integration
):
    """Test setting time calls async_setup_daily_schedule()."""
    coordinator = init_integration.runtime_data

    with (
        patch.object(coordinator, "async_setup_daily_schedule") as mock_setup_schedule,
        patch.object(hass.config_entries, "async_update_entry"),
    ):
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "time.test_cleanup_run_at", ATTR_TIME: "05:15:00"},
            blocking=True,
        )

        await hass.async_block_till_done()

        mock_setup_schedule.assert_called_once()


async def test_time_entity_validates_format(hass: HomeAssistant, init_integration):
    """Test HH:MM format validation."""
    state = hass.states.get("time.test_cleanup_run_at")
    assert state is not None, "Time entity should exist"

    state_time = dt_time.fromisoformat(state.state)
    assert isinstance(state_time, dt_time), "Should have valid time object"
    assert state_time.second == 0, "Seconds should be zero"


async def test_time_entity_attributes(hass: HomeAssistant, init_integration):
    """Test time entity attributes and configuration."""
    registry = er.async_get(hass)

    entry = registry.async_get("time.test_cleanup_run_at")
    assert entry is not None, "Time entity should exist in registry"
    assert (
        entry.unique_id == f"{init_integration.entry_id}_run_at"
    ), "Should have correct unique_id format"
    assert (
        entry.entity_category == EntityCategory.CONFIG
    ), "Should have CONFIG entity category"

    state = hass.states.get("time.test_cleanup_run_at")
    assert state is not None, "Time entity state should exist"


async def test_time_entity_device_info(hass: HomeAssistant, init_integration):
    """Test that time entity is linked to the correct device."""
    registry = er.async_get(hass)

    entry = registry.async_get("time.test_cleanup_run_at")
    assert entry is not None, "Time entity should exist"
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


async def test_time_entity_unique_id_stable(hass: HomeAssistant, init_integration):
    """Test that time entity unique ID remains stable."""
    registry = er.async_get(hass)
    entry_id = init_integration.entry_id

    entity_id = registry.async_get_entity_id(TIME_DOMAIN, DOMAIN, f"{entry_id}_run_at")
    assert entity_id is not None, "Time entity should be found by unique_id"
    assert entity_id == "time.test_cleanup_run_at", "Should have correct entity_id"


async def test_time_entity_updates_from_coordinator(
    hass: HomeAssistant, init_integration
):
    """Test that time entity reflects coordinator config changes."""
    coordinator = init_integration.runtime_data

    await coordinator.async_update_config_value(CONF_RUN_AT, "06:45")
    await hass.async_block_till_done()

    state = hass.states.get("time.test_cleanup_run_at")
    assert state is not None, "Time entity should still exist"

    state_time = dt_time.fromisoformat(state.state)
    assert (
        state_time.hour == 6 and state_time.minute == 45
    ), "State should reflect updated coordinator config"


@pytest.mark.parametrize(
    ("time_value", "expected_hour", "expected_minute"),
    [
        ("00:00:00", 0, 0),
        ("23:59:00", 23, 59),
        ("12:00:00", 12, 0),
        ("03:15:00", 3, 15),
    ],
)
async def test_time_entity_boundary_values(
    hass: HomeAssistant, init_integration, time_value, expected_hour, expected_minute
):
    """Test setting boundary time values (00:00 to 23:59)."""
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "time.test_cleanup_run_at", ATTR_TIME: time_value},
        blocking=True,
    )

    state = hass.states.get("time.test_cleanup_run_at")
    assert state is not None, "Time entity should exist"

    state_time = dt_time.fromisoformat(state.state)
    assert (
        state_time.hour == expected_hour and state_time.minute == expected_minute
    ), f"Should accept time value {time_value}"


async def test_time_entity_multiple_updates(hass: HomeAssistant, init_integration):
    """Test multiple time updates work correctly."""
    coordinator = init_integration.runtime_data

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "time.test_cleanup_run_at",
            ATTR_TIME: "10:30:00",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("time.test_cleanup_run_at")
    state_time = dt_time.fromisoformat(state.state)
    assert state_time.hour == 10 and state_time.minute == 30, "Should update to 10:30"

    coordinator_time = coordinator.run_at
    assert (
        coordinator_time.hour == 10 and coordinator_time.minute == 30
    ), "Coordinator should have 10:30"

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "time.test_cleanup_run_at",
            ATTR_TIME: "15:45:00",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("time.test_cleanup_run_at")
    state_time = dt_time.fromisoformat(state.state)
    assert state_time.hour == 15 and state_time.minute == 45, "Should update to 15:45"

    coordinator_time = coordinator.run_at
    assert (
        coordinator_time.hour == 15 and coordinator_time.minute == 45
    ), "Coordinator should have 15:45"


async def test_time_entity_availability(hass: HomeAssistant, init_integration):
    """Test time entity availability based on coordinator."""
    coordinator = init_integration.runtime_data

    state = hass.states.get("time.test_cleanup_run_at")
    assert state.state != "unavailable", "Should be available when coordinator is ready"

    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    state = hass.states.get("time.test_cleanup_run_at")
    assert (
        state.state != "unavailable"
    ), "Time entity should remain available even with no coordinator data"


async def test_time_entity_default_value(hass: HomeAssistant):
    """Test default time value when not specified in config."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry_default = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Default Time",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
            "dry_run": True,
            "max_deletes": 100,
        },
        entry_id="test_default_time_entry",
    )
    entry_default.add_to_hass(hass)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
    ):
        assert await hass.config_entries.async_setup(entry_default.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("time.test_default_time_run_at")
    assert state is not None, "Time entity should exist"

    state_time = dt_time.fromisoformat(state.state)
    assert state_time.hour == 3 and state_time.minute == 15, "Should default to 03:15"


async def test_time_entity_formats_hh_mm_correctly(
    hass: HomeAssistant, init_integration
):
    """Test that time is stored as HH:MM string in config."""
    coordinator = init_integration.runtime_data

    with (
        patch.object(coordinator, "async_update_config_value") as mock_update_config,
        patch.object(hass.config_entries, "async_update_entry"),
    ):
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "time.test_cleanup_run_at", ATTR_TIME: "07:09:00"},
            blocking=True,
        )

        mock_update_config.assert_called_once_with(CONF_RUN_AT, "07:09")


async def test_time_entity_strips_seconds(hass: HomeAssistant, init_integration):
    """Test that seconds are stripped from time value."""
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "time.test_cleanup_run_at", ATTR_TIME: "08:30:59"},
        blocking=True,
    )

    state = hass.states.get("time.test_cleanup_run_at")
    assert state is not None, "Time entity should exist"

    state_time = dt_time.fromisoformat(state.state)
    assert state_time.second == 0, "Seconds should be stripped to 0"


async def test_time_entity_scheduler_reschedule_on_change(
    hass: HomeAssistant, init_integration
):
    """Test that changing time triggers scheduler update."""
    coordinator = init_integration.runtime_data

    with (
        patch.object(coordinator, "async_setup_daily_schedule") as mock_schedule,
        patch.object(hass.config_entries, "async_update_entry"),
    ):
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "time.test_cleanup_run_at", ATTR_TIME: "09:00:00"},
            blocking=True,
        )

        await hass.async_block_till_done()

        mock_schedule.assert_called_once()
