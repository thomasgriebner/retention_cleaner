from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    EntityCategory,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RetentionCleanerCoordinator


SENSOR_DEFS = [
    ("total_files", "Total files", "files", "mdi:file-multiple", None, None, None),
    ("older_than_retention", "Older than retention", "files", "mdi:file-clock-outline", None, None, None),
    ("deleted_last_run", "Deleted last cleanup", "files", "mdi:delete-outline", None, None, None),
    ("deleted_bytes_last_run", "Deleted bytes last cleanup", UnitOfInformation.BYTES, "mdi:delete-circle-outline", None, SensorDeviceClass.DATA_SIZE, SensorStateClass.MEASUREMENT),
    ("last_scan", "Last scan", None, "mdi:folder-search", EntityCategory.DIAGNOSTIC, None, None),
    ("last_cleanup", "Last cleanup", None, "mdi:broom", EntityCategory.DIAGNOSTIC, None, None),
    ("last_scan_duration_ms", "Last scan duration", "ms", "mdi:timer-outline", EntityCategory.DIAGNOSTIC, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT),
    ("last_cleanup_duration_ms", "Last cleanup duration", "ms", "mdi:timer-check-outline", EntityCategory.DIAGNOSTIC, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RetentionCleanerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            RetentionCleanerSensor(coordinator, entry, key, name, unit, icon, category, device_class, state_class)
            for key, name, unit, icon, category, device_class, state_class in SENSOR_DEFS
        ]
    )


class RetentionCleanerSensor(CoordinatorEntity[RetentionCleanerCoordinator], SensorEntity):
    def __init__(
        self,
        coordinator: RetentionCleanerCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        unit: str | None,
        icon: str,
        category: EntityCategory | None = None,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_{key}"

        title = entry.title or coordinator.base_path
        self._attr_name = f"{title} {name}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        
        if category:
            self._attr_entity_category = category
        
        if device_class:
            self._attr_device_class = device_class
        
        if state_class:
            self._attr_state_class = state_class

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=title,
            manufacturer="Retention Cleaner",
            model="Folder retention rule",
            configuration_url=coordinator.base_path,
        )

    @property
    def native_value(self) -> Any:
        return (self.coordinator.data or {}).get(self._key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data or {}
        return {
            "base_path": d.get("base_path"),
            "pattern": d.get("pattern"),
            "retention_days": d.get("retention_days"),
        }
