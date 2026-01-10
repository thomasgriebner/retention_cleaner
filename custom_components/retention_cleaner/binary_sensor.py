from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RetentionCleanerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RetentionCleanerCoordinator = entry.runtime_data
    async_add_entities([RetentionCleanerPathAvailable(coordinator, entry)])


class RetentionCleanerPathAvailable(
    RestoreEntity, CoordinatorEntity[RetentionCleanerCoordinator], BinarySensorEntity
):
    def __init__(
        self, coordinator: RetentionCleanerCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_path_available"

        title = entry.title or coordinator.base_path
        self._attr_name = f"{title} Path available"

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
            else:
                self._restored_last_state = None
        except Exception:
            # Gracefully handle restore failures
            self._restored_last_state = None

    @property
    def is_on(self) -> bool | None:
        """Return true if the path is available or restored state."""
        current_value = (self.coordinator.data or {}).get("path_available")

        if current_value is not None:
            return bool(current_value)

        restored_state = getattr(self, "_restored_last_state", None)
        if restored_state is not None and restored_state not in (
            "unknown",
            "unavailable",
        ):
            return restored_state == "on"

        return None
