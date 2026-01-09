"""Test retention_cleaner button entities."""

from unittest.mock import AsyncMock

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.retention_cleaner.const import DOMAIN


async def test_button_setup(hass: HomeAssistant, init_integration):
    """Test button entities are created correctly."""
    scan_button = hass.states.get("button.test_cleanup_scan_now")
    assert scan_button is not None

    cleanup_button = hass.states.get("button.test_cleanup_run_cleanup")
    assert cleanup_button is not None


async def test_button_attributes(hass: HomeAssistant, init_integration):
    """Test button attributes."""
    registry = er.async_get(hass)

    scan_entry = registry.async_get("button.test_cleanup_scan_now")
    assert scan_entry is not None
    assert scan_entry.unique_id == f"{init_integration.entry_id}_scan_now"

    cleanup_entry = registry.async_get("button.test_cleanup_run_cleanup")
    assert cleanup_entry is not None
    assert cleanup_entry.unique_id == f"{init_integration.entry_id}_cleanup_now"


async def test_scan_button_press(hass: HomeAssistant, init_integration):
    """Test pressing the scan button triggers a scan."""
    coordinator = init_integration.runtime_data
    coordinator.async_scan_now = AsyncMock(
        return_value={
            "total_files": 50,
            "older_than_retention": 10,
            "last_scan": "2024-01-01T12:00:00",
        }
    )

    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_cleanup_scan_now"},
        blocking=True,
    )

    # Verify scan was triggered
    coordinator.async_scan_now.assert_called_once()


async def test_cleanup_button_press(hass: HomeAssistant, init_integration):
    """Test pressing the cleanup button triggers a cleanup."""
    coordinator = init_integration.runtime_data
    coordinator.async_run_cleanup_now = AsyncMock(
        return_value={
            "deleted_last_run": 5,
            "deleted_bytes_last_run": 5120,
            "last_cleanup": "2024-01-01T02:00:00",
        }
    )

    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_cleanup_run_cleanup"},
        blocking=True,
    )

    # Verify cleanup was triggered with manual trigger
    coordinator.async_run_cleanup_now.assert_called_once_with(triggered_by="manual")


async def test_button_availability(hass: HomeAssistant, init_integration):
    """Test button availability based on coordinator."""
    coordinator = init_integration.runtime_data

    scan_state = hass.states.get("button.test_cleanup_scan_now")
    assert scan_state.state != "unavailable"

    cleanup_state = hass.states.get("button.test_cleanup_run_cleanup")
    assert cleanup_state.state != "unavailable"

    coordinator.last_update_success = False
    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    scan_state = hass.states.get("button.test_cleanup_scan_now")
    assert scan_state.state == "unavailable"

    cleanup_state = hass.states.get("button.test_cleanup_run_cleanup")
    assert cleanup_state.state == "unavailable"


async def test_button_device_info(hass: HomeAssistant, init_integration):
    """Test that buttons are linked to the correct device."""
    registry = er.async_get(hass)

    scan_entry = registry.async_get("button.test_cleanup_scan_now")
    assert scan_entry is not None
    assert scan_entry.device_id is not None

    cleanup_entry = registry.async_get("button.test_cleanup_run_cleanup")
    assert cleanup_entry is not None
    assert cleanup_entry.device_id == scan_entry.device_id  # Same device

    # Verify device info
    device_registry = hass.helpers.device_registry.async_get(hass)
    device = device_registry.async_get(scan_entry.device_id)
    assert device is not None
    assert device.name == "Test Cleanup"
    assert device.model == "/media/test"
    assert device.manufacturer == "Retention Cleaner"
    assert (DOMAIN, init_integration.entry_id) in device.identifiers


async def test_button_entity_category(hass: HomeAssistant, init_integration):
    """Test that buttons have correct entity category."""
    registry = er.async_get(hass)

    # Both buttons should have no category (user-facing controls)
    scan_entry = registry.async_get("button.test_cleanup_scan_now")
    assert scan_entry is not None
    assert scan_entry.entity_category is None  # User-facing control

    cleanup_entry = registry.async_get("button.test_cleanup_run_cleanup")
    assert cleanup_entry is not None
    assert cleanup_entry.entity_category is None  # User-facing control


async def test_button_unique_ids_stable(hass: HomeAssistant, init_integration):
    """Test that button unique IDs remain stable."""
    registry = er.async_get(hass)
    entry_id = init_integration.entry_id

    # Find entities by unique_id
    scan_entity = registry.async_get_entity_id("button", DOMAIN, f"{entry_id}_scan_now")
    assert scan_entity is not None
    assert scan_entity == "button.test_cleanup_scan_now"

    cleanup_entity = registry.async_get_entity_id(
        "button", DOMAIN, f"{entry_id}_cleanup_now"
    )
    assert cleanup_entity is not None
    assert cleanup_entity == "button.test_cleanup_run_cleanup"


async def test_button_press_error_handling(hass: HomeAssistant, init_integration):
    """Test button press handles errors gracefully."""
    coordinator = init_integration.runtime_data

    coordinator.async_scan_now = AsyncMock(side_effect=Exception("Scan failed"))

    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_cleanup_scan_now"},
        blocking=True,
    )

    coordinator.async_run_cleanup_now = AsyncMock(
        side_effect=Exception("Cleanup failed")
    )

    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_cleanup_run_cleanup"},
        blocking=True,
    )


async def test_multiple_button_presses(hass: HomeAssistant, init_integration):
    """Test multiple button presses work correctly."""
    coordinator = init_integration.runtime_data
    coordinator.async_scan_now = AsyncMock(return_value={"total_files": 100})
    coordinator.async_run_cleanup_now = AsyncMock(return_value={"deleted_last_run": 5})

    for _ in range(3):
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.test_cleanup_scan_now"},
            blocking=True,
        )

    assert coordinator.async_scan_now.call_count == 3

    for _ in range(2):
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.test_cleanup_run_cleanup"},
            blocking=True,
        )

    assert coordinator.async_run_cleanup_now.call_count == 2
