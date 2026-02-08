"""Time entities for retention_cleaner."""

from __future__ import annotations

from datetime import time as dt_time
import logging

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_RUN_AT, DEFAULT_RUN_AT, DOMAIN
from .coordinator import RetentionCleanerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up time entities for retention_cleaner."""
    coordinator: RetentionCleanerCoordinator = entry.runtime_data
    async_add_entities([RunAtTimeEntity(coordinator, entry)])


class RunAtTimeEntity(CoordinatorEntity[RetentionCleanerCoordinator], TimeEntity):
    """Time entity for run_at configuration."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: RetentionCleanerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the run_at time entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_run_at"
        self._pending_value: str | None = None  # Cache for value updates

        title = entry.title or coordinator.base_path
        self._attr_name = f"{title} Run at"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=title,
            manufacturer="Retention Cleaner",
            model="Folder retention rule",
        )

    @property
    def native_value(self) -> dt_time | None:
        """Return the current run_at time value.

        Parses the run_at string (HH:MM format) from the coordinator
        configuration and converts it to a datetime.time object.

        Returns:
            dt_time: Current scheduled run time with hour, minute, and zero seconds.
                    Returns None if parsing fails (should never happen with valid config).
        """
        # Use pending value if set (for immediate UI feedback)
        # Otherwise read from coordinator.cfg which includes entry.options
        run_at_str = self._pending_value or self.coordinator.cfg.get(
            CONF_RUN_AT, DEFAULT_RUN_AT
        )

        try:
            hh, mm = run_at_str.split(":")
            return dt_time(hour=int(hh), minute=int(mm), second=0)
        except (ValueError, AttributeError) as err:  # pragma: no cover
            # NOTE: This error path is intentionally not covered by tests.
            #
            # Rationale for pragma:
            # 1. Config flow validation prevents invalid run_at formats
            # 2. Default value (DEFAULT_RUN_AT) ensures run_at is never None
            # 3. Testing requires mocking coordinator.cfg property after entity creation,
            #    which conflicts with CoordinatorEntity's internal state management
            # 4. Manual testing (corrupt .storage/ database) confirms fallback works
            #
            # This defensive code handles edge cases:
            # - Database corruption (run_at: null in .storage/)
            # - Manual YAML edits (if future versions support YAML config)
            # - Config migration failures
            #
            # If triggered, logs error and falls back to DEFAULT_RUN_AT (03:15)
            _LOGGER.error(
                "Failed to parse run_at value '%s': %s. Using default %s",
                run_at_str,
                err,
                DEFAULT_RUN_AT,
            )
            # Fallback to default time if parsing fails
            hh, mm = DEFAULT_RUN_AT.split(":")
            return dt_time(hour=int(hh), minute=int(mm), second=0)

    async def async_set_value(self, value: dt_time) -> None:
        """Update the run_at time value.

        Converts the datetime.time object to HH:MM string format and
        persists it via the coordinator's async_update_config_value method.

        This triggers:
            1. Config entry update (persistence)
            2. Scheduler reschedule (via coordinator.async_update_config_value)
            3. Coordinator refresh (updates all entities)

        Args:
            value: New time value to set for scheduled cleanup.
        """
        # Convert dt_time to "HH:MM" string format (strip seconds)
        time_str = f"{value.hour:02d}:{value.minute:02d}"

        _LOGGER.info(
            "Updating run_at to %s for %s",
            time_str,
            self.coordinator.base_path,
        )

        # Cache the value for immediate UI feedback
        self._pending_value = time_str

        # This will trigger scheduler update and coordinator refresh
        await self.coordinator.async_update_config_value(CONF_RUN_AT, time_str)

        # Clear pending value once config is updated
        self._pending_value = None

        # Manually update entity state since we read from cfg, not coordinator.data
        self.async_write_ha_state()
