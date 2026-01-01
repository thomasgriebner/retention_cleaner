from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RetentionCleanerCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: RetentionCleanerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RetentionCleanerPathAvailable(coordinator, entry.entry_id)])


class RetentionCleanerPathAvailable(CoordinatorEntity[RetentionCleanerCoordinator], BinarySensorEntity):
    def __init__(self, coordinator: RetentionCleanerCoordinator, entry_id: str):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_path_available"
        folder = coordinator.base_path.split("/")[-1] or coordinator.base_path
        self._attr_name = f"Retention Cleaner {folder} Path available"

    @property
    def is_on(self):
        return bool((self.coordinator.data or {}).get("path_available"))
