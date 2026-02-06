from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    EntityCategory,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RetentionCleanerCoordinator

SENSOR_DEFS = [
    (
        "total_files",
        "Total files",
        "files",
        "mdi:file-multiple",
        None,
        None,
        None,
        None,
        None,
    ),
    (
        "older_than_retention",
        "Older than retention",
        "files",
        "mdi:file-clock-outline",
        None,
        None,
        None,
        None,
        None,
    ),
    (
        "deleted_last_run",
        "Deleted last cleanup",
        "files",
        "mdi:delete-outline",
        None,
        None,
        None,
        None,
        None,
    ),
    (
        "deleted_bytes_last_run",
        "Deleted size last cleanup",
        UnitOfInformation.BYTES,
        "mdi:delete-circle-outline",
        None,
        SensorDeviceClass.DATA_SIZE,
        SensorStateClass.MEASUREMENT,
        UnitOfInformation.MEGABYTES,
        2,
    ),
    (
        "total_folder_size_bytes",
        "Total folder size",
        UnitOfInformation.BYTES,
        "mdi:folder-multiple",
        None,
        SensorDeviceClass.DATA_SIZE,
        SensorStateClass.MEASUREMENT,
        UnitOfInformation.MEGABYTES,
        2,
    ),
    (
        "older_than_retention_size_bytes",
        "Older than retention size",
        UnitOfInformation.BYTES,
        "mdi:delete-clock",
        None,
        SensorDeviceClass.DATA_SIZE,
        SensorStateClass.MEASUREMENT,
        UnitOfInformation.MEGABYTES,
        2,
    ),
    (
        "last_scan",
        "Last scan",
        None,
        "mdi:folder-search",
        EntityCategory.DIAGNOSTIC,
        SensorDeviceClass.TIMESTAMP,
        None,
        None,
        None,
    ),
    (
        "last_cleanup",
        "Last cleanup",
        None,
        "mdi:broom",
        EntityCategory.DIAGNOSTIC,
        SensorDeviceClass.TIMESTAMP,
        None,
        None,
        None,
    ),
    (
        "last_scan_duration_ms",
        "Last scan duration",
        "ms",
        "mdi:timer-outline",
        EntityCategory.DIAGNOSTIC,
        SensorDeviceClass.DURATION,
        SensorStateClass.MEASUREMENT,
        None,
        None,
    ),
    (
        "last_cleanup_duration_ms",
        "Last cleanup duration",
        "ms",
        "mdi:timer-check-outline",
        EntityCategory.DIAGNOSTIC,
        SensorDeviceClass.DURATION,
        SensorStateClass.MEASUREMENT,
        None,
        None,
    ),
    (
        "base_path",
        "Base Path",
        None,
        "mdi:folder",
        EntityCategory.DIAGNOSTIC,
        None,
        None,
        None,
        None,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RetentionCleanerCoordinator = entry.runtime_data
    async_add_entities(
        [
            RetentionCleanerSensor(
                coordinator,
                entry,
                key,
                name,
                unit,
                icon,
                category,
                device_class,
                state_class,
                suggested_unit,
                suggested_precision,
            )
            for key, name, unit, icon, category, device_class, state_class, suggested_unit, suggested_precision in SENSOR_DEFS
        ]
    )


class RetentionCleanerSensor(
    RestoreEntity, CoordinatorEntity[RetentionCleanerCoordinator], SensorEntity
):
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
        suggested_unit: str | None = None,
        suggested_precision: int | None = None,
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

        if suggested_unit:
            self._attr_suggested_unit_of_measurement = suggested_unit

        if suggested_precision is not None:
            self._attr_suggested_display_precision = suggested_precision

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=title,
            manufacturer="Retention Cleaner",
            model="Folder retention rule",
        )

    async def async_added_to_hass(self) -> None:
        """Entity has been added to hass."""
        await super().async_added_to_hass()

        try:
            if (last_state := await self.async_get_last_state()) is not None:
                self._restored_last_state = last_state.state
                self._restored_attributes = last_state.attributes or {}
            else:
                self._restored_last_state = None
                self._restored_attributes = {}
        except Exception:
            # Gracefully handle restore failures
            self._restored_last_state = None
            self._restored_attributes = {}

    @property
    def native_value(self) -> Any:
        """Return the current value or restored value."""
        # Special handling for base_path sensor - get from coordinator.base_path
        if self._key == "base_path":
            return self.coordinator.base_path

        current_value = (self.coordinator.data or {}).get(self._key)

        if current_value is not None:
            return current_value

        restored_state = getattr(self, "_restored_last_state", None)
        if restored_state is not None and restored_state not in (
            "unknown",
            "unavailable",
        ):
            # Timestamp sensors: convert string to datetime for HA validation
            if self._key in ("last_scan", "last_cleanup"):
                if isinstance(restored_state, str):
                    try:
                        from datetime import datetime

                        # Try to parse ISO format timestamp
                        return datetime.fromisoformat(
                            restored_state.replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        return None
                return restored_state

            # Numeric sensors: convert to int with fallback
            if self._key in (
                "total_files",
                "older_than_retention",
                "deleted_last_run",
                "deleted_bytes_last_run",
                "total_folder_size_bytes",
                "older_than_retention_size_bytes",
                "last_scan_duration_ms",
                "last_cleanup_duration_ms",
            ):
                try:
                    if isinstance(restored_state, str) and restored_state.isdigit():
                        return int(restored_state)
                    if isinstance(restored_state, int | float):
                        return int(restored_state)
                    return 0
                except (ValueError, TypeError):
                    return 0

            # Other sensors: return as-is
            return restored_state

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return empty dict - config values are now proper CONFIG entities."""
        return {}
