from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RetentionCleanerCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: RetentionCleanerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RetentionCleanerScanNowButton(coordinator, entry.entry_id)])


class RetentionCleanerScanNowButton(CoordinatorEntity[RetentionCleanerCoordinator], ButtonEntity):
    def __init__(self, coordinator: RetentionCleanerCoordinator, entry_id: str):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_scan_now"
        folder = coordinator.base_path.split("/")[-1] or coordinator.base_path
        self._attr_name = f"Retention Cleaner {folder} Scan now"

    async def async_press(self) -> None:
        await self.coordinator.async_run_scan_now()
