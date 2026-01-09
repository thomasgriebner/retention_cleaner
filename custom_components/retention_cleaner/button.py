from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

_LOGGER = logging.getLogger(__name__)

from .const import DOMAIN
from .coordinator import RetentionCleanerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RetentionCleanerCoordinator = entry.runtime_data
    async_add_entities(
        [
            RetentionCleanerScanNowButton(coordinator, entry),
            RetentionCleanerCleanupNowButton(coordinator, entry),
        ]
    )


class _BaseRetentionCleanerButton(
    CoordinatorEntity[RetentionCleanerCoordinator], ButtonEntity
):
    def __init__(
        self,
        coordinator: RetentionCleanerCoordinator,
        entry: ConfigEntry,
        suffix: str,
        label: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"

        title = entry.title or coordinator.base_path
        self._attr_name = f"{title} {label}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=title,
            manufacturer="Retention Cleaner",
            model="Folder retention rule",
        )


class RetentionCleanerScanNowButton(_BaseRetentionCleanerButton):
    def __init__(
        self, coordinator: RetentionCleanerCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "scan_now", "Scan now")

    async def async_press(self) -> None:
        _LOGGER.info("Manual scan triggered for %s", self.coordinator.base_path)
        await self.coordinator.async_run_scan_now()


class RetentionCleanerCleanupNowButton(_BaseRetentionCleanerButton):
    def __init__(
        self, coordinator: RetentionCleanerCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "cleanup_now", "Run cleanup")

    async def async_press(self) -> None:
        _LOGGER.info("Manual cleanup triggered for %s", self.coordinator.base_path)
        await self.coordinator.async_run_cleanup_now()
