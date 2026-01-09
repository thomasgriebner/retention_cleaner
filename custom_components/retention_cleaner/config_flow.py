from __future__ import annotations

import logging
import re

from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

from .const import (
    CONF_BASE_PATH,
    CONF_DRY_RUN,
    CONF_MAX_DELETES,
    CONF_PATTERN,
    CONF_RETENTION_DAYS,
    CONF_RUN_AT,
    DEFAULT_DRY_RUN,
    DEFAULT_MAX_DELETES,
    DEFAULT_PATTERN,
    DEFAULT_RETENTION_DAYS,
    DEFAULT_RUN_AT,
    DOMAIN,
)

TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def _validate_base_path(value: str) -> str:
    value = (value or "").strip()
    # Safety guard for MVP: only allow /media paths
    if not value.startswith("/media/"):
        _LOGGER.warning("Invalid base path provided (not under /media/): %s", value)
        raise vol.Invalid("base_path_not_media")
    return value.rstrip("/")


def _validate_run_at(value: str) -> str:
    value = (value or "").strip()
    if not TIME_RE.match(value):
        _LOGGER.warning("Invalid time format provided: %s (expected HH:MM)", value)
        raise vol.Invalid("run_at_invalid")
    hh, mm = value.split(":")
    if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
        _LOGGER.warning("Invalid time value provided: %s", value)
        raise vol.Invalid("run_at_invalid")
    return value


def _validate_pattern(value: str) -> str:
    """Validate glob pattern and warn about dangerous patterns."""
    value = (value or "*").strip()

    # Check for EXTREMELY dangerous patterns that match ALL files
    EXTREMELY_DANGEROUS = ["*", "**/*"]
    if value in EXTREMELY_DANGEROUS:
        _LOGGER.warning("Extremely dangerous pattern '%s' matches ALL files", value)
        raise vol.Invalid("pattern_too_broad")

    # Check for invalid syntax
    if "***" in value:
        _LOGGER.warning("Invalid pattern syntax: triple asterisk in '%s'", value)
        raise vol.Invalid("pattern_invalid_syntax")

    # Check for unclosed brackets/braces
    if value.count("{") != value.count("}"):
        _LOGGER.warning("Invalid pattern: unclosed braces in '%s'", value)
        raise vol.Invalid("pattern_invalid_syntax")

    if value.count("[") != value.count("]"):
        _LOGGER.warning("Invalid pattern: unclosed brackets in '%s'", value)
        raise vol.Invalid("pattern_invalid_syntax")

    return value


class RetentionCleanerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Retention Cleaner."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                base_path = _validate_base_path(user_input[CONF_BASE_PATH])
                pattern = _validate_pattern(
                    user_input.get(CONF_PATTERN, DEFAULT_PATTERN)
                )
                run_at = _validate_run_at(user_input.get(CONF_RUN_AT, DEFAULT_RUN_AT))

                data = {
                    CONF_BASE_PATH: base_path,
                    CONF_PATTERN: pattern,
                    CONF_RETENTION_DAYS: int(
                        user_input.get(CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS)
                    ),
                    CONF_RUN_AT: run_at,
                    CONF_DRY_RUN: bool(user_input.get(CONF_DRY_RUN, DEFAULT_DRY_RUN)),
                    CONF_MAX_DELETES: int(
                        user_input.get(CONF_MAX_DELETES, DEFAULT_MAX_DELETES)
                    ),
                }

                title = base_path.split("/")[-1] or base_path
                _LOGGER.info(
                    "Creating config entry for path: %s (pattern: %s, retention: %d days)",
                    base_path,
                    data[CONF_PATTERN],
                    data[CONF_RETENTION_DAYS],
                )
                return self.async_create_entry(title=title, data=data)

            except vol.Invalid as e:
                # Map our validation codes to translation keys
                error_key = str(e)
                if error_key in (
                    "base_path_not_media",
                    "run_at_invalid",
                    "pattern_too_broad",
                    "pattern_invalid_syntax",
                ):
                    errors["base"] = error_key
                else:
                    _LOGGER.error("Unexpected validation error: %s", str(e))
                    errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_PATH): str,
                vol.Optional(CONF_PATTERN, default=DEFAULT_PATTERN): str,
                vol.Optional(
                    CONF_RETENTION_DAYS, default=DEFAULT_RETENTION_DAYS
                ): vol.Coerce(int),
                vol.Optional(CONF_RUN_AT, default=DEFAULT_RUN_AT): str,
                vol.Optional(CONF_DRY_RUN, default=DEFAULT_DRY_RUN): bool,
                vol.Optional(CONF_MAX_DELETES, default=DEFAULT_MAX_DELETES): vol.Coerce(
                    int
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return RetentionCleanerOptionsFlow(config_entry)


class RetentionCleanerOptionsFlow(config_entries.OptionsFlow):
    """Options flow to edit an existing Retention Cleaner entry."""

    def __init__(self, config_entry):
        super().__init__()

    async def async_step_init(self, user_input=None):
        errors: dict[str, str] = {}

        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            try:
                base_path = _validate_base_path(user_input[CONF_BASE_PATH])
                pattern = _validate_pattern(
                    user_input.get(CONF_PATTERN, DEFAULT_PATTERN)
                )
                run_at = _validate_run_at(user_input.get(CONF_RUN_AT, DEFAULT_RUN_AT))

                _LOGGER.info(
                    "Updating config for path: %s (pattern: %s, retention: %d days)",
                    base_path,
                    pattern,
                    int(user_input.get(CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS)),
                )
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_BASE_PATH: base_path,
                        CONF_PATTERN: pattern,
                        CONF_RETENTION_DAYS: int(
                            user_input.get(CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS)
                        ),
                        CONF_RUN_AT: run_at,
                        CONF_DRY_RUN: bool(
                            user_input.get(CONF_DRY_RUN, DEFAULT_DRY_RUN)
                        ),
                        CONF_MAX_DELETES: int(
                            user_input.get(CONF_MAX_DELETES, DEFAULT_MAX_DELETES)
                        ),
                    },
                )

            except vol.Invalid as e:
                error_key = str(e)
                if error_key in (
                    "base_path_not_media",
                    "run_at_invalid",
                    "pattern_too_broad",
                    "pattern_invalid_syntax",
                ):
                    errors["base"] = error_key
                else:
                    _LOGGER.error(
                        "Unexpected validation error in options flow: %s", str(e)
                    )
                    errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_BASE_PATH, default=current.get(CONF_BASE_PATH, "")
                ): str,
                vol.Optional(
                    CONF_PATTERN, default=current.get(CONF_PATTERN, DEFAULT_PATTERN)
                ): str,
                vol.Optional(
                    CONF_RETENTION_DAYS,
                    default=current.get(CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS),
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_RUN_AT, default=current.get(CONF_RUN_AT, DEFAULT_RUN_AT)
                ): str,
                vol.Optional(
                    CONF_DRY_RUN, default=current.get(CONF_DRY_RUN, DEFAULT_DRY_RUN)
                ): bool,
                vol.Optional(
                    CONF_MAX_DELETES,
                    default=current.get(CONF_MAX_DELETES, DEFAULT_MAX_DELETES),
                ): vol.Coerce(int),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
