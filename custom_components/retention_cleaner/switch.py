"""Switch platform for retention_cleaner integration."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DRY_RUN, CONF_REMOVE_EMPTY_FOLDERS, DOMAIN
from .coordinator import RetentionCleanerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    coordinator: RetentionCleanerCoordinator = entry.runtime_data

    entities = [
        DryRunSwitch(coordinator, entry),
        RemoveEmptyFoldersSwitch(coordinator, entry),
    ]

    async_add_entities(entities)


class RetentionCleanerSwitchEntity(
    CoordinatorEntity[RetentionCleanerCoordinator], SwitchEntity
):
    """Base class for retention_cleaner switch entities."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: RetentionCleanerCoordinator,
        entry: ConfigEntry,
        config_key: str,
        name_suffix: str,
        friendly_name_suffix: str,
        icon: str,
    ) -> None:
        """Initialize switch entity."""
        super().__init__(coordinator)
        self._config_key = config_key
        self._friendly_name_suffix = friendly_name_suffix
        title = entry.title or coordinator.base_path
        # Name for entity_id generation (shorter)
        self._attr_name = f"{title} {name_suffix}"
        self._attr_unique_id = f"{entry.entry_id}_{config_key}"
        self._attr_icon = icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=title,
            manufacturer="Retention Cleaner",
            model="Folder retention rule",
        )
        self._title = title

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        # After registration, update the friendly name to the longer version
        self._attr_name = f"{self._title} {self._friendly_name_suffix}"

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return bool(self.coordinator.cfg.get(self._config_key, False))

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await self.coordinator.async_update_config_value(self._config_key, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self.coordinator.async_update_config_value(self._config_key, False)
        self.async_write_ha_state()


class DryRunSwitch(RetentionCleanerSwitchEntity):
    """Switch to control dry run mode."""

    def __init__(
        self,
        coordinator: RetentionCleanerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize dry run switch."""
        super().__init__(
            coordinator,
            entry,
            CONF_DRY_RUN,
            "Dry run",
            "Dry run",
            "mdi:test-tube",
        )


class RemoveEmptyFoldersSwitch(RetentionCleanerSwitchEntity):
    """Switch to control empty folder removal."""

    def __init__(
        self,
        coordinator: RetentionCleanerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize remove empty folders switch."""
        super().__init__(
            coordinator,
            entry,
            CONF_REMOVE_EMPTY_FOLDERS,
            "Remove empty folders",
            "Remove empty folders after cleanup",
            "mdi:folder-remove",
        )
