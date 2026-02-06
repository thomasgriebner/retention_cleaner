"""Text entities for retention_cleaner."""

from __future__ import annotations

import logging

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ALL_FILES_PATTERN,
    CONF_EXCEPT_EXTENSIONS,
    CONF_ONLY_EXTENSIONS,
    CONF_PATTERN,
    DOMAIN,
)
from .coordinator import RetentionCleanerCoordinator

_LOGGER = logging.getLogger(__name__)


def _validate_pattern(value: str) -> None:
    """Validate glob pattern for safety.

    Args:
        value: Pattern string to validate.

    Raises:
        ServiceValidationError: If pattern is too dangerous or invalid.

    Safety checks:
        - Reject '*' (matches all files in base directory)
        - Reject '**/*' (matches all files recursively)
        - Validate basic glob syntax
    """
    if not value:  # Empty is allowed (when using extension filters)
        return

    # Reject dangerous patterns that match all files
    if value == "*":
        raise ServiceValidationError(
            "Pattern '*' is too broad and dangerous. Use a more specific pattern like '*.jpg' or extension filters.",
            translation_domain=DOMAIN,
            translation_key="pattern_too_broad",
        )

    if value == ALL_FILES_PATTERN:
        raise ServiceValidationError(
            "Pattern '**/*' is too broad and dangerous. Use a more specific pattern like '**/*.jpg' or extension filters.",
            translation_domain=DOMAIN,
            translation_key="pattern_too_broad",
        )

    # Basic syntax validation - check for obviously invalid patterns
    # Multiple consecutive asterisks (except ** for recursive glob)
    if "***" in value:
        raise ServiceValidationError(
            "Invalid pattern syntax: '***' is not valid. Use '**' for recursive matching.",
            translation_domain=DOMAIN,
            translation_key="pattern_invalid_syntax",
        )


def _validate_extensions(value: str) -> None:
    """Validate extension list for safety.

    Args:
        value: Comma-separated extension list to validate.

    Raises:
        ServiceValidationError: If any extension is invalid.

    Safety checks:
        - Extensions must start with '.' (dot)
        - No wildcards (* ? [ ])
        - No path separators (/ \\)
        - At least one character after dot
    """
    if not value:  # Empty is allowed
        return

    # Parse extensions (same logic as coordinator)
    extensions = [ext.strip() for ext in value.split(",")]
    extensions = [ext for ext in extensions if ext]  # Filter empty

    for ext in extensions:
        # Must start with dot
        if not ext.startswith("."):
            raise ServiceValidationError(
                f"Extension '{ext}' must start with a dot (e.g., '.mp4').",
                translation_domain=DOMAIN,
                translation_key="extension_must_start_with_dot",
            )

        # Must have at least one character after dot
        if len(ext) < 2:
            raise ServiceValidationError(
                f"Extension '{ext}' is too short. Must have at least one character after the dot (e.g., '.mp4').",
                translation_domain=DOMAIN,
                translation_key="extension_too_short",
            )

        # No wildcards allowed in extensions
        if any(wildcard in ext for wildcard in ["*", "?", "[", "]"]):
            raise ServiceValidationError(
                f"Extension '{ext}' cannot contain wildcards. Extensions must be exact (e.g., '.mp4').",
                translation_domain=DOMAIN,
                translation_key="extension_no_wildcards",
            )

        # No path separators allowed
        if "/" in ext or "\\" in ext:
            raise ServiceValidationError(
                f"Extension '{ext}' cannot contain path separators. Use simple extensions like '.mp4'.",
                translation_domain=DOMAIN,
                translation_key="extension_no_paths",
            )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up text entities for retention_cleaner."""
    coordinator: RetentionCleanerCoordinator = entry.runtime_data

    async_add_entities(
        [
            PatternTextEntity(coordinator, entry),
            OnlyExtensionsTextEntity(coordinator, entry),
            ExceptExtensionsTextEntity(coordinator, entry),
        ]
    )


class RetentionCleanerTextEntity(
    CoordinatorEntity[RetentionCleanerCoordinator], TextEntity
):
    """Base text entity for retention_cleaner configuration."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = TextMode.TEXT
    _attr_native_max = 255

    def __init__(
        self,
        coordinator: RetentionCleanerCoordinator,
        entry: ConfigEntry,
        config_key: str,
        name_suffix: str,
    ) -> None:
        """Initialize the text entity.

        Args:
            coordinator: The coordinator managing this entity.
            entry: The config entry for this integration instance.
            config_key: Configuration key (e.g., CONF_PATTERN).
            name_suffix: Human-readable name suffix (e.g., "Pattern").
        """
        super().__init__(coordinator)
        self._entry = entry
        self._config_key = config_key
        self._attr_unique_id = f"{entry.entry_id}_{config_key}"

        title = entry.title or coordinator.base_path
        self._attr_name = f"{title} {name_suffix}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=title,
            manufacturer="Retention Cleaner",
            model="Folder retention rule",
        )

    def _get_cfg_value(self, key: str) -> str:
        """Get configuration value from entry.

        Args:
            key: Configuration key to retrieve.

        Returns:
            str: Configuration value, or empty string if not set.
        """
        cfg = {**self._entry.data, **self._entry.options}
        return cfg.get(key, "")

    @property
    def native_value(self) -> str:
        """Return the current value from coordinator config.

        Returns:
            str: Current configuration value, or empty string if not set.
        """
        return self._get_cfg_value(self._config_key)

    async def async_set_value(self, value: str) -> None:
        """Set the text value and update configuration.

        Validates the value, checks mutual exclusion rules, and persists
        the change via coordinator.async_update_config_value.

        Args:
            value: New text value to set.

        Raises:
            ServiceValidationError: If validation fails or mutual exclusion violated.
        """
        # Subclasses implement specific validation
        await self._validate_value(value)

        # Check cross-field validation (mutual exclusion)
        await self._validate_mutual_exclusion(value)

        # Persist via coordinator
        _LOGGER.info(
            "Updating %s to '%s' for %s",
            self._config_key,
            value,
            self.coordinator.base_path,
        )
        await self.coordinator.async_update_config_value(self._config_key, value)

    async def _validate_value(self, value: str) -> None:
        """Validate the value (implemented by subclasses).

        Args:
            value: Value to validate.

        Raises:
            ServiceValidationError: If validation fails.
        """
        raise NotImplementedError

    async def _validate_mutual_exclusion(self, value: str) -> None:
        """Validate mutual exclusion rules (implemented by subclasses).

        Args:
            value: Value being set.

        Raises:
            ServiceValidationError: If mutual exclusion violated.
        """
        pass  # pragma: no cover - Template method, always overridden by subclasses


class PatternTextEntity(RetentionCleanerTextEntity):
    """Text entity for pattern configuration."""

    def __init__(
        self,
        coordinator: RetentionCleanerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the pattern text entity."""
        super().__init__(coordinator, entry, CONF_PATTERN, "Pattern")

    async def _validate_value(self, value: str) -> None:
        """Validate pattern syntax and safety.

        Args:
            value: Pattern to validate.

        Raises:
            ServiceValidationError: If pattern is invalid or dangerous.
        """
        _validate_pattern(value)

    async def _validate_mutual_exclusion(self, value: str) -> None:
        """Ensure pattern is not set when extensions are configured.

        Args:
            value: Pattern being set.

        Raises:
            ServiceValidationError: If extensions are already set.
        """
        # Allow empty pattern (when using extensions)
        if not value:
            return

        # Check if extensions are set (read from entry config)
        only_ext = self._get_cfg_value(CONF_ONLY_EXTENSIONS)
        except_ext = self._get_cfg_value(CONF_EXCEPT_EXTENSIONS)

        if only_ext or except_ext:
            raise ServiceValidationError(
                "Cannot set pattern when extension filters (only_extensions or except_extensions) are configured. Clear extensions first.",
                translation_domain=DOMAIN,
                translation_key="cannot_combine_pattern_and_extensions",
            )


class OnlyExtensionsTextEntity(RetentionCleanerTextEntity):
    """Text entity for only_extensions configuration."""

    def __init__(
        self,
        coordinator: RetentionCleanerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the only_extensions text entity."""
        super().__init__(coordinator, entry, CONF_ONLY_EXTENSIONS, "Only extensions")

    async def _validate_value(self, value: str) -> None:
        """Validate extension list.

        Args:
            value: Comma-separated extension list to validate.

        Raises:
            ServiceValidationError: If any extension is invalid.
        """
        _validate_extensions(value)

    async def _validate_mutual_exclusion(self, value: str) -> None:
        """Ensure only_extensions is not set when pattern or except_extensions are configured.

        Args:
            value: Extension list being set.

        Raises:
            ServiceValidationError: If pattern or except_extensions are set.
        """
        # Allow empty value (clearing the filter)
        if not value:
            return

        # Check if pattern is set (read from entry config)
        pattern = self._get_cfg_value(CONF_PATTERN)
        if pattern:
            raise ServiceValidationError(
                "Cannot set extension filters when pattern is configured. Clear pattern first.",
                translation_domain=DOMAIN,
                translation_key="cannot_combine_pattern_and_extensions",
            )

        # Check if except_extensions is set
        except_ext = self._get_cfg_value(CONF_EXCEPT_EXTENSIONS)
        if except_ext:
            raise ServiceValidationError(
                "Cannot use both only_extensions and except_extensions. Choose one filter type.",
                translation_domain=DOMAIN,
                translation_key="cannot_use_both_only_and_except",
            )


class ExceptExtensionsTextEntity(RetentionCleanerTextEntity):
    """Text entity for except_extensions configuration."""

    def __init__(
        self,
        coordinator: RetentionCleanerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the except_extensions text entity."""
        super().__init__(
            coordinator, entry, CONF_EXCEPT_EXTENSIONS, "Except extensions"
        )

    async def _validate_value(self, value: str) -> None:
        """Validate extension list.

        Args:
            value: Comma-separated extension list to validate.

        Raises:
            ServiceValidationError: If any extension is invalid.
        """
        _validate_extensions(value)

    async def _validate_mutual_exclusion(self, value: str) -> None:
        """Ensure except_extensions is not set when pattern or only_extensions are configured.

        Args:
            value: Extension list being set.

        Raises:
            ServiceValidationError: If pattern or only_extensions are set.
        """
        # Allow empty value (clearing the filter)
        if not value:
            return

        # Check if pattern is set (read from entry config)
        pattern = self._get_cfg_value(CONF_PATTERN)
        if pattern:
            raise ServiceValidationError(
                "Cannot set extension filters when pattern is configured. Clear pattern first.",
                translation_domain=DOMAIN,
                translation_key="cannot_combine_pattern_and_extensions",
            )

        # Check if only_extensions is set
        only_ext = self._get_cfg_value(CONF_ONLY_EXTENSIONS)
        if only_ext:
            raise ServiceValidationError(
                "Cannot use both only_extensions and except_extensions. Choose one filter type.",
                translation_domain=DOMAIN,
                translation_key="cannot_use_both_only_and_except",
            )
