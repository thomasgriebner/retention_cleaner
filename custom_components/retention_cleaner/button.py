from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RetentionCleanerCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: RetentionCleanerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            RetentionCleanerScanNowButton(coordinator, entry.entry_id),
            RetentionCleanerCleanupNowButton(coordinator, entry.entry_id),
        ]
    )


class _BaseRetentionCleanerButton(CoordinatorEntity[RetentionCleanerCoordinator], ButtonEntity):
    def __init__(self, coordinator: RetentionCleanerCoordinator, entry_id: str, unique_suffix: str, label: str):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{unique_suffix}"
        folder = coordinator.base_path.split("/")[-1] or coordinator.base_path
        self._attr_name = f"Retention Cleaner {folder} {label}"


class RetentionCleanerScanNowButton(_BaseRetentionCleanerButton):
    def __init__(self, coordinator: RetentionCleanerCoordinator, entry_id: str):
        super().__init__(coordinator, entry_id, "scan_now", "Scan now")

    async def async_press(self) -> None:
        await self.coordinator.async_run_scan_now()


class RetentionCleanerCleanupNowButton(_BaseRetentionCleanerButton):
    def __init__(self, coordinator: RetentionCleanerCoordinator, entry_id: str):
        super().__init__(coordinator, entry_id, "cleanup_now", "Run cleanup")

    async def async_press(self) -> None:
        await self.coordinator.async_run_cleanup_now()
