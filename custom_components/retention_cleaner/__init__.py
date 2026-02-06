from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .coordinator import RetentionCleanerCoordinator

_LOGGER = logging.getLogger(__name__)

# This integration is configured via config entries only (no YAML config).
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[str] = [
    "sensor",
    "binary_sensor",
    "button",
    "number",
    "text",
    "time",
    "switch",
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Retention Cleaner (YAML setup not supported)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Retention Cleaner from a config entry."""
    _LOGGER.info(
        "Setting up Retention Cleaner for path: %s",
        entry.data.get("base_path", "unknown"),
    )

    coordinator = RetentionCleanerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Daily scheduled cleanup (based on run_at from config)
    await coordinator.async_setup_daily_schedule()

    _LOGGER.debug(
        "Retention Cleaner setup complete for entry: %s (platforms: %s)",
        entry.title,
        PLATFORMS,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Retention Cleaner for entry: %s", entry.title)

    coordinator: RetentionCleanerCoordinator | None = getattr(
        entry, "runtime_data", None
    )
    if coordinator:
        await coordinator.async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        _LOGGER.debug("Successfully unloaded entry: %s", entry.title)
    return unload_ok
