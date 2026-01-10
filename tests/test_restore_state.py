"""Test state restoration for retention cleaner sensors."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import StoredState
import pytest


async def test_sensor_restore_numeric_value(hass: HomeAssistant, init_integration):
    """Test sensor restores numeric values correctly."""
    # Mock restored states at the HA framework level
    restore_data = {
        f"{init_integration.entry_id}_total_files": StoredState(
            state="42",
            attributes={
                "base_path": "/media/test",
                "pattern": "*.jpg",
                "retention_days": 7,
            },
            last_changed=None,
            last_updated=None,
        )
    }

    with patch(
        "homeassistant.helpers.restore_state.RestoreStateData.async_get_stored_states",
        return_value=restore_data,
    ):
        # Reload integration to trigger restoration
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Check restored state
        state = hass.states.get("sensor.test_cleanup_total_files")
        assert state is not None
        assert state.state == "42"
        assert state.attributes["base_path"] == "/media/test"
        assert state.attributes["pattern"] == "*.jpg"
        assert state.attributes["retention_days"] == 7


async def test_sensor_restore_timestamp_value(hass: HomeAssistant, init_integration):
    """Test sensor restores timestamp values correctly."""
    restore_data = {
        f"{init_integration.entry_id}_last_scan": StoredState(
            state="2024-01-07T15:30:45",
            attributes={"base_path": "/media/test"},
            last_changed=None,
            last_updated=None,
        )
    }

    with patch(
        "homeassistant.helpers.restore_state.RestoreStateData.async_get_stored_states",
        return_value=restore_data,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Timestamp should be restored as-is
        state = hass.states.get("sensor.test_cleanup_last_scan")
        assert state is not None
        assert state.state == "2024-01-07T15:30:45"


async def test_sensor_no_restored_state(hass: HomeAssistant, init_integration):
    """Test sensor behavior when no restored state exists."""
    # Mock empty restore data
    with patch(
        "homeassistant.helpers.restore_state.RestoreStateData.async_get_stored_states",
        return_value={},
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Should show unavailable when no current data and no restored state
        state = hass.states.get("sensor.test_cleanup_total_files")
        assert state is not None
        assert state.state in [STATE_UNAVAILABLE, "0", None]


async def test_sensor_current_data_overrides_restored(
    hass: HomeAssistant, init_integration
):
    """Test that current coordinator data overrides restored state."""
    # Set up restored state
    restore_data = {
        f"{init_integration.entry_id}_total_files": StoredState(
            state="42",
            attributes={},
            last_changed=None,
            last_updated=None,
        )
    }

    # Mock coordinator to have current data
    coordinator = init_integration.runtime_data
    coordinator.data = {"total_files": 123}  # Current data should win

    with patch(
        "homeassistant.helpers.restore_state.RestoreStateData.async_get_stored_states",
        return_value=restore_data,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Current data should override restored state
        state = hass.states.get("sensor.test_cleanup_total_files")
        assert state is not None
        assert state.state == "123"  # Current data, not restored "42"


@pytest.mark.parametrize("invalid_state", ["", "not_a_number", "abc", "-5"])
async def test_sensor_invalid_numeric_restoration(
    hass: HomeAssistant, init_integration, invalid_state
):
    """Test sensor handles invalid restored values gracefully."""
    restore_data = {
        f"{init_integration.entry_id}_total_files": StoredState(
            state=invalid_state,
            attributes={},
            last_changed=None,
            last_updated=None,
        )
    }

    with patch(
        "homeassistant.helpers.restore_state.RestoreStateData.async_get_stored_states",
        return_value=restore_data,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Should fall back to 0 for invalid numeric values
        state = hass.states.get("sensor.test_cleanup_total_files")
        assert state is not None
        assert state.state == "0"


@pytest.mark.parametrize("ignored_state", [STATE_UNKNOWN, STATE_UNAVAILABLE])
async def test_sensor_unknown_unavailable_state_ignored(
    hass: HomeAssistant, init_integration, ignored_state
):
    """Test that unknown/unavailable states are ignored during restoration."""
    restore_data = {
        f"{init_integration.entry_id}_total_files": StoredState(
            state=ignored_state,
            attributes={},
            last_changed=None,
            last_updated=None,
        )
    }

    with patch(
        "homeassistant.helpers.restore_state.RestoreStateData.async_get_stored_states",
        return_value=restore_data,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Should ignore unknown/unavailable and show current state
        state = hass.states.get("sensor.test_cleanup_total_files")
        assert state is not None
        # Should not restore the unknown/unavailable value
        assert state.state != ignored_state


async def test_binary_sensor_restore_on_state(hass: HomeAssistant, init_integration):
    """Test binary sensor restores 'on' state correctly."""
    restore_data = {
        f"{init_integration.entry_id}_path_available": StoredState(
            state="on",
            attributes={},
            last_changed=None,
            last_updated=None,
        )
    }

    with patch(
        "homeassistant.helpers.restore_state.RestoreStateData.async_get_stored_states",
        return_value=restore_data,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Should restore the on state
        state = hass.states.get("binary_sensor.test_cleanup_path_available")
        assert state is not None
        assert state.state == "on"


async def test_binary_sensor_restore_off_state(hass: HomeAssistant, init_integration):
    """Test binary sensor restores 'off' state correctly."""
    restore_data = {
        f"{init_integration.entry_id}_path_available": StoredState(
            state="off",
            attributes={},
            last_changed=None,
            last_updated=None,
        )
    }

    with patch(
        "homeassistant.helpers.restore_state.RestoreStateData.async_get_stored_states",
        return_value=restore_data,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Should restore the off state
        state = hass.states.get("binary_sensor.test_cleanup_path_available")
        assert state is not None
        assert state.state == "off"


async def test_binary_sensor_current_data_overrides_restored(
    hass: HomeAssistant, init_integration
):
    """Test that current coordinator data overrides restored state for binary sensor."""
    # Set up restored state as off
    restore_data = {
        f"{init_integration.entry_id}_path_available": StoredState(
            state="off",
            attributes={},
            last_changed=None,
            last_updated=None,
        )
    }

    # Mock coordinator to have current data
    coordinator = init_integration.runtime_data
    coordinator.data = {"path_available": True}  # Current data should win

    with patch(
        "homeassistant.helpers.restore_state.RestoreStateData.async_get_stored_states",
        return_value=restore_data,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Current data should override restored state
        state = hass.states.get("binary_sensor.test_cleanup_path_available")
        assert state is not None
        assert state.state == "on"  # Current data, not restored "off"


async def test_binary_sensor_no_restored_state(hass: HomeAssistant, init_integration):
    """Test binary sensor behavior when no restored state exists."""
    # Mock empty restore data
    with patch(
        "homeassistant.helpers.restore_state.RestoreStateData.async_get_stored_states",
        return_value={},
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Should show unavailable when no data and no restored state
        state = hass.states.get("binary_sensor.test_cleanup_path_available")
        assert state is not None
        assert state.state in [STATE_UNAVAILABLE, "off"]


@pytest.mark.parametrize("ignored_state", [STATE_UNKNOWN, STATE_UNAVAILABLE])
async def test_binary_sensor_unknown_state_ignored(
    hass: HomeAssistant, init_integration, ignored_state
):
    """Test that unknown/unavailable states are ignored for binary sensor."""
    restore_data = {
        f"{init_integration.entry_id}_path_available": StoredState(
            state=ignored_state,
            attributes={},
            last_changed=None,
            last_updated=None,
        )
    }

    with patch(
        "homeassistant.helpers.restore_state.RestoreStateData.async_get_stored_states",
        return_value=restore_data,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Should ignore unknown/unavailable states
        state = hass.states.get("binary_sensor.test_cleanup_path_available")
        assert state is not None
        assert state.state != ignored_state


async def test_attribute_restoration_priority(hass: HomeAssistant, init_integration):
    """Test that current attributes override restored ones correctly."""
    restore_data = {
        f"{init_integration.entry_id}_total_files": StoredState(
            state="10",
            attributes={
                "base_path": "/media/old_path",
                "pattern": "*.old",
                "retention_days": 3,
            },
            last_changed=None,
            last_updated=None,
        )
    }

    # Mock coordinator with current attributes
    coordinator = init_integration.runtime_data
    coordinator.data = {
        "total_files": 50,
        "base_path": "/media/current",
        "pattern": "*.new",
        "retention_days": 7,
    }

    with patch(
        "homeassistant.helpers.restore_state.RestoreStateData.async_get_stored_states",
        return_value=restore_data,
    ):
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Current attributes should take precedence
        state = hass.states.get("sensor.test_cleanup_total_files")
        assert state is not None
        assert state.state == "50"  # Current value
        assert state.attributes["base_path"] == "/media/current"
        assert state.attributes["pattern"] == "*.new"
        assert state.attributes["retention_days"] == 7


async def test_restoration_exception_handling(hass: HomeAssistant, init_integration):
    """Test graceful handling of restoration failures."""
    # Mock async_get_last_state to raise an exception
    with patch(
        "homeassistant.helpers.restore_state.RestoreStateData.async_get_stored_states",
        side_effect=Exception("Restore failed"),
    ):
        # Should not crash during setup
        await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

        # Integration should still work normally without restoration
        state = hass.states.get("sensor.test_cleanup_total_files")
        assert state is not None
        # Should show current state or unavailable, not crash
