from __future__ import annotations

from homeassistant.core import HomeAssistant


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Retention Cleaner (YAML setup not supported)."""
    return True