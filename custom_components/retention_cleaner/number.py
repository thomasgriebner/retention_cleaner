"""Number entities for retention_cleaner."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_KEEP_MINIMUM_FILES,
    CONF_MAX_DELETES,
    CONF_MAX_FILES_IN_FOLDER,
    CONF_RETENTION_DAYS,
    DOMAIN,
)
from .coordinator import RetentionCleanerCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class RetentionCleanerNumberEntityDescription(NumberEntityDescription):
    """Describes a retention_cleaner number entity."""

    config_key: str


NUMBER_ENTITY_DESCRIPTIONS: tuple[RetentionCleanerNumberEntityDescription, ...] = (
    RetentionCleanerNumberEntityDescription(
        key="retention_days",
        translation_key="retention_days",
        name="Retention days",
        icon="mdi:calendar-clock",
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_min_value=1,
        native_max_value=3650,
        native_step=1,
        native_unit_of_measurement="days",
        config_key=CONF_RETENTION_DAYS,
    ),
    RetentionCleanerNumberEntityDescription(
        key="max_deletes",
        translation_key="max_deletes",
        name="Max deletes",
        icon="mdi:delete-sweep",
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_min_value=1,
        native_max_value=10000,
        native_step=1,
        native_unit_of_measurement="files",
        config_key=CONF_MAX_DELETES,
    ),
    RetentionCleanerNumberEntityDescription(
        key="keep_minimum_files",
        translation_key="keep_minimum_files",
        name="Keep minimum files",
        icon="mdi:file-lock",
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=10000,
        native_step=1,
        native_unit_of_measurement="files",
        config_key=CONF_KEEP_MINIMUM_FILES,
    ),
    RetentionCleanerNumberEntityDescription(
        key="max_files_in_folder",
        translation_key="max_files_in_folder",
        name="Max files in folder",
        icon="mdi:file-alert",
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=1000000,
        native_step=1,
        native_unit_of_measurement="files",
        config_key=CONF_MAX_FILES_IN_FOLDER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities for retention_cleaner."""
    coordinator: RetentionCleanerCoordinator = entry.runtime_data
    async_add_entities(
        RetentionCleanerNumberEntity(coordinator, entry, description)
        for description in NUMBER_ENTITY_DESCRIPTIONS
    )


class RetentionCleanerNumberEntity(
    CoordinatorEntity[RetentionCleanerCoordinator], NumberEntity
):
    """Number entity for retention_cleaner configuration."""

    entity_description: RetentionCleanerNumberEntityDescription

    def __init__(
        self,
        coordinator: RetentionCleanerCoordinator,
        entry: ConfigEntry,
        description: RetentionCleanerNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        title = entry.title or coordinator.base_path
        self._attr_name = f"{title} {description.name}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=title,
            manufacturer="Retention Cleaner",
            model="Folder retention rule",
        )

    @property
    def native_value(self) -> float:
        """Return the current value from coordinator."""
        value = getattr(self.coordinator, self.entity_description.key)
        return float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Update the configuration value."""
        int_value = int(value)
        _LOGGER.info(
            "Updating %s to %d for %s",
            self.entity_description.key,
            int_value,
            self.coordinator.base_path,
        )
        await self.coordinator.async_update_config_value(
            self.entity_description.config_key, int_value
        )
