from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RetentionCleanerCoordinator


SENSOR_DEFS = [
    ("total_files", "Total files", "files"),
    ("older_than_retention", "Older than retention", "files"),
    ("deleted_last_run", "Deleted last cleanup", "files"),
    ("last_scan", "Last scan", None),
    ("last_cleanup", "Last cleanup", None),
]


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: RetentionCleanerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            RetentionCleanerSensor(coordinator, entry.entry_id, key, name, unit)
            for key, name, unit in SENSOR_DEFS
        ]
    )


class RetentionCleanerSensor(CoordinatorEntity[RetentionCleanerCoordinator], SensorEntity):
    def __init__(
        self,
        coordinator: RetentionCleanerCoordinator,
        entry_id: str,
        key: str,
        name: str,
        unit: str | None,
    ):
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{entry_id}_{key}"

        folder = coordinator.base_path.split("/")[-1] or coordinator.base_path
        self._attr_name = f"Retention Cleaner {folder} {name}"
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self._key)

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data or {}
        return {
            "base_path": d.get("base_path"),
            "pattern": d.get("pattern"),
            "retention_days": d.get("retention_days"),
        }
