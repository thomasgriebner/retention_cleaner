"""Test retention_cleaner button entities."""

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

    # Store initial last_scan time (may be None initially)
    initial_last_scan = coordinator.last_scan

    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_cleanup_scan_now"},
        blocking=True,
    )

    # Verify scan was triggered - last_scan should now be set
    assert coordinator.last_scan is not None
    # If there was an initial value, it should be different
    if initial_last_scan is not None:
        assert coordinator.last_scan != initial_last_scan


async def test_cleanup_button_press(hass: HomeAssistant, init_integration):
    """Test pressing the cleanup button triggers a cleanup."""
    coordinator = init_integration.runtime_data

    # Store initial last_cleanup time (may be None initially)
    initial_last_cleanup = coordinator.last_cleanup

    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_cleanup_run_cleanup"},
        blocking=True,
    )

    # Verify cleanup was triggered - last_cleanup should now be set
    assert coordinator.last_cleanup is not None
    # If there was an initial value, it should be different
    if initial_last_cleanup is not None:
        assert coordinator.last_cleanup != initial_last_cleanup


async def test_button_availability(hass: HomeAssistant, init_integration):
    """Test button availability based on coordinator."""
    coordinator = init_integration.runtime_data

    scan_state = hass.states.get("button.test_cleanup_scan_now")
    # Buttons always have 'unknown' state in Home Assistant
    assert scan_state.state == "unknown"

    cleanup_state = hass.states.get("button.test_cleanup_run_cleanup")
    assert cleanup_state.state == "unknown"  # Buttons always have 'unknown' state

    # Test button functionality instead of availability states
    # Buttons should be functional when coordinator is working
    initial_scan_time = coordinator.last_scan

    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_cleanup_scan_now"},
        blocking=True,
    )

    # Verify button worked
    assert coordinator.last_scan != initial_scan_time


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
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, init_integration.entry_id)}
    )
    assert device is not None
    assert device.name == "Test Cleanup"
    assert device.model == "Folder retention rule"
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
    from unittest.mock import patch

    # Mock the filesystem to cause errors
    with patch("pathlib.Path.glob", side_effect=OSError("Permission denied")):
        # This should not crash the button press, errors should be handled gracefully
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.test_cleanup_scan_now"},
            blocking=True,
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

    # Test multiple scan button presses - each should update last_scan
    initial_last_scan = coordinator.last_scan

    for _ in range(3):
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.test_cleanup_scan_now"},
            blocking=True,
        )
        # Each scan should update the timestamp
        assert coordinator.last_scan != initial_last_scan
        initial_last_scan = coordinator.last_scan

    # Test multiple cleanup button presses - each should update last_cleanup
    initial_last_cleanup = coordinator.last_cleanup

    for _ in range(2):
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.test_cleanup_run_cleanup"},
            blocking=True,
        )
        # Each cleanup should update the timestamp
        assert coordinator.last_cleanup != initial_last_cleanup
        initial_last_cleanup = coordinator.last_cleanup
