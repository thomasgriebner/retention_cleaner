from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RetentionCleanerCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: RetentionCleanerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RetentionCleanerPathAvailable(coordinator, entry)])


class RetentionCleanerPathAvailable(
    CoordinatorEntity[RetentionCleanerCoordinator], BinarySensorEntity
):
    def __init__(self, coordinator: RetentionCleanerCoordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_path_available"

        title = entry.title or coordinator.base_path
        self._attr_name = f"Retention {title} Path available"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Retention – {title}",
            manufacturer="Retention Cleaner",
            model="Folder retention rule",
        )

    @property
    def is_on(self):
        return bool((self.coordinator.data or {}).get("path_available"))
