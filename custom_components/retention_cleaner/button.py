from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RetentionCleanerCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: RetentionCleanerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            RetentionCleanerScanNowButton(coordinator, entry),
            RetentionCleanerCleanupNowButton(coordinator, entry),
        ]
    )


class _BaseRetentionCleanerButton(
    CoordinatorEntity[RetentionCleanerCoordinator], ButtonEntity
):
    def __init__(self, coordinator: RetentionCleanerCoordinator, entry, suffix: str, label: str):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"

        title = entry.title or coordinator.base_path
        self._attr_name = f"Retention {title} {label}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Retention – {title}",
            manufacturer="Retention Cleaner",
            model="Folder retention rule",
        )


class RetentionCleanerScanNowButton(_BaseRetentionCleanerButton):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "scan_now", "Scan now")

    async def async_press(self) -> None:
        await self.coordinator.async_run_scan_now()


class RetentionCleanerCleanupNowButton(_BaseRetentionCleanerButton):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "cleanup_now", "Run cleanup")

    async def async_press(self) -> None:
        await self.coordinator.async_run_cleanup_now()
