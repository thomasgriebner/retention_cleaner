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
    CONF_EXCEPT_EXTENSIONS,
    CONF_KEEP_MINIMUM_FILES,
    CONF_MAX_DELETES,
    CONF_MAX_FILES_IN_FOLDER,
    CONF_ONLY_EXTENSIONS,
    CONF_PATTERN,
    CONF_REMOVE_EMPTY_FOLDERS,
    CONF_RETENTION_DAYS,
    CONF_RUN_AT,
    DEFAULT_DRY_RUN,
    DEFAULT_KEEP_MINIMUM_FILES,
    DEFAULT_MAX_DELETES,
    DEFAULT_MAX_FILES_IN_FOLDER,
    DEFAULT_PATTERN,
    DEFAULT_REMOVE_EMPTY_FOLDERS,
    DEFAULT_RETENTION_DAYS,
    DEFAULT_RUN_AT,
    DOMAIN,
)

ALLOWED_BASE_PATHS = ("/media/", "/share/")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def _map_validation_error_to_fields(error_key: str) -> dict[str, str]:
    """Map validation error codes to form field names.

    Args:
        error_key: Validation error code (e.g., "base_path_not_media")

    Returns:
        dict: Mapping of field names to error codes

    Example:
        >>> _map_validation_error_to_fields("extension_must_start_with_dot")
        {'only_extensions': 'extension_must_start_with_dot',
         'except_extensions': 'extension_must_start_with_dot'}
    """
    errors = {}

    if error_key == "base_path_not_media":
        errors[CONF_BASE_PATH] = error_key
    elif error_key == "run_at_invalid":
        errors[CONF_RUN_AT] = error_key
    elif error_key in ("pattern_too_broad", "pattern_invalid_syntax"):
        errors[CONF_PATTERN] = error_key
    elif error_key in ("retention_days_negative", "retention_days_too_large"):
        errors[CONF_RETENTION_DAYS] = error_key
    elif error_key in ("keep_minimum_negative", "keep_minimum_too_large"):
        errors[CONF_KEEP_MINIMUM_FILES] = error_key
    elif error_key in ("max_files_negative", "max_files_too_large"):
        errors[CONF_MAX_FILES_IN_FOLDER] = error_key
    elif error_key in (
        "extension_must_start_with_dot",
        "extension_no_wildcards",
        "extension_no_paths",
        "extension_too_short",
    ):
        # Extension validation errors - apply to both fields
        errors[CONF_ONLY_EXTENSIONS] = error_key
        errors[CONF_EXCEPT_EXTENSIONS] = error_key
    elif error_key in (
        "must_set_pattern_or_extensions",
        "cannot_combine_pattern_and_extensions",
        "cannot_use_both_only_and_except",
    ):
        # Mutual exclusion errors - apply to base
        errors["base"] = error_key
    else:
        errors["base"] = "unknown"

    return errors


def _validate_base_path(value: str) -> str:
    """Validate base path is under /media/ or /share/ and contains no symlinks.

    Security: Rejects symlinks at any level to prevent TOCTOU attacks.
    """
    value = (value or "").strip()

    # Basic check: must start with /media/ or /share/
    if not any(value.startswith(path) for path in ALLOWED_BASE_PATHS):
        _LOGGER.warning(
            "Invalid base path provided (not under allowed paths): %s", value
        )
        raise vol.Invalid("base_path_not_media")

    # Security check: resolve path to prevent traversal attacks
    from pathlib import Path

    try:
        path_obj = Path(value)

        # Security: Check for symlinks at ANY level
        # This prevents TOCTOU (Time of Check Time of Use) attacks
        if path_obj.is_symlink():
            _LOGGER.warning("Symlink detected at path: %s", value)
            raise vol.Invalid("base_path_not_media")

        # Check all parent directories for symlinks
        for parent in path_obj.parents:
            if parent.is_symlink():
                _LOGGER.warning("Symlink detected in parent path: %s", parent)
                raise vol.Invalid("base_path_not_media")

        # After validation, resolve and ensure still under allowed paths
        resolved_path = str(path_obj.resolve())
        if not any(resolved_path.startswith(path) for path in ALLOWED_BASE_PATHS):
            _LOGGER.warning(
                "Path traversal attempt: %s resolves to %s", value, resolved_path
            )
            raise vol.Invalid("base_path_not_media")

    except OSError as e:
        _LOGGER.warning("Invalid path: %s (%s)", value, e)
        raise vol.Invalid("base_path_not_media") from e

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


def _validate_pattern(value: str, allow_empty: bool = False) -> str:
    """Validate glob pattern and warn about dangerous patterns.

    Args:
        value: Pattern string to validate.
        allow_empty: If True, empty patterns are allowed (for extension filtering mode).

    Returns:
        str: Validated pattern.

    Raises:
        vol.Invalid: If pattern is invalid or dangerous.
    """
    value = (value or "").strip()

    # Empty pattern handling
    if not value:
        if allow_empty:
            return value
        # Empty pattern not allowed in standalone mode
        _LOGGER.warning("Empty pattern provided")
        raise vol.Invalid("pattern_invalid_syntax")

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


def _validate_extensions(value: str) -> str:
    """Validate extension list format.

    Args:
        value: Comma-separated list of extensions (e.g., ".mp4,.jpg")

    Returns:
        str: Validated and normalized extension list.

    Raises:
        vol.Invalid: If extension format is invalid.
    """
    value = (value or "").strip()

    # Empty is valid (optional field)
    if not value:
        return value

    # Parse extensions
    extensions = [ext.strip() for ext in value.split(",")]
    extensions = [ext for ext in extensions if ext]  # Remove empty strings

    if not extensions:
        return ""

    # Validate each extension
    for ext in extensions:
        # Must start with a dot
        if not ext.startswith("."):
            _LOGGER.warning(
                "Invalid extension '%s': must start with a dot (e.g., '.mp4')", ext
            )
            raise vol.Invalid("extension_must_start_with_dot")

        # Must not contain wildcards
        if "*" in ext or "?" in ext:
            _LOGGER.warning("Invalid extension '%s': wildcards not allowed", ext)
            raise vol.Invalid("extension_no_wildcards")

        # Must not contain path separators
        if "/" in ext or "\\" in ext:
            _LOGGER.warning("Invalid extension '%s': path separators not allowed", ext)
            raise vol.Invalid("extension_no_paths")

        # Must have at least one character after the dot
        if len(ext) < 2:
            _LOGGER.warning("Invalid extension '%s': too short", ext)
            raise vol.Invalid("extension_too_short")

    return value


def _validate_keep_minimum_files(value: int, max_deletes: int) -> int:
    """Validate keep_minimum_files setting.

    Args:
        value: Number of minimum files to keep.
        max_deletes: Maximum number of files that can be deleted per run.

    Returns:
        int: Validated minimum files value.

    Raises:
        vol.Invalid: If value is out of range (0-10000).
    """
    if value < 0:
        _LOGGER.warning("Invalid keep_minimum_files: %d (must be >= 0)", value)
        raise vol.Invalid("keep_minimum_negative")
    if value > 10000:
        _LOGGER.warning("Invalid keep_minimum_files: %d (must be <= 10000)", value)
        raise vol.Invalid("keep_minimum_too_large")

    # Warning if keep_minimum > max_deletes (unusual but valid)
    if value > max_deletes:
        _LOGGER.warning(
            "keep_minimum_files (%d) exceeds max_deletes (%d) - this may prevent deletions",
            value,
            max_deletes,
        )

    return value


def _validate_max_files_in_folder(value: int, keep_minimum_files: int) -> int:
    """Validate max_files_in_folder setting.

    Args:
        value: Maximum number of files to keep in folder (0 = disabled).
        keep_minimum_files: Minimum number of files to keep.

    Returns:
        int: Validated max files value.

    Raises:
        vol.Invalid: If value is out of range (0-1,000,000).
    """
    if value < 0:
        _LOGGER.warning("Invalid max_files_in_folder: %d (must be >= 0)", value)
        raise vol.Invalid("max_files_negative")
    if value > 1000000:
        _LOGGER.warning("Invalid max_files_in_folder: %d (must be <= 1,000,000)", value)
        raise vol.Invalid("max_files_too_large")

    # Warning if max_files < keep_minimum (max_files takes priority but it's confusing)
    if value > 0 and keep_minimum_files > 0 and value < keep_minimum_files:
        _LOGGER.warning(
            "max_files_in_folder (%d) is less than keep_minimum_files (%d) - max_files takes priority",
            value,
            keep_minimum_files,
        )

    return value


def _validate_pattern_and_extensions(user_input: dict) -> dict:
    """Validate mutual exclusion between pattern and extension filters.

    Args:
        user_input: User configuration dictionary.

    Returns:
        dict: Validated configuration with normalized values.

    Raises:
        vol.Invalid: If validation rules are violated.
    """
    pattern = user_input.get(CONF_PATTERN, "").strip()
    only_ext = user_input.get(CONF_ONLY_EXTENSIONS, "").strip()
    except_ext = user_input.get(CONF_EXCEPT_EXTENSIONS, "").strip()

    has_extensions = bool(only_ext or except_ext)

    # UX Fix: Treat DEFAULT_PATTERN as empty when extensions are provided
    # This allows extension filters to override the default pattern value
    # without requiring users to manually clear the field
    if has_extensions and pattern == DEFAULT_PATTERN:
        pattern = ""

    has_pattern = bool(pattern)

    # Rule 1: At least one must be set
    if not has_pattern and not has_extensions:
        _LOGGER.warning("No pattern or extensions configured")
        raise vol.Invalid("must_set_pattern_or_extensions")

    # Rule 2: Cannot use both pattern and extensions
    if has_pattern and has_extensions:
        _LOGGER.warning(
            "Cannot combine pattern '%s' with extensions (only=%s, except=%s)",
            pattern,
            only_ext,
            except_ext,
        )
        raise vol.Invalid("cannot_combine_pattern_and_extensions")

    # Rule 3: Cannot use both only_extensions and except_extensions
    if only_ext and except_ext:
        _LOGGER.warning(
            "Cannot use both only_extensions and except_extensions: only=%s, except=%s",
            only_ext,
            except_ext,
        )
        raise vol.Invalid("cannot_use_both_only_and_except")

    # Validate pattern if set (allow empty when using extensions)
    if has_pattern:
        pattern = _validate_pattern(pattern, allow_empty=False)
    elif has_extensions:
        # Empty pattern is OK when using extension filters
        pattern = ""

    # Validate extensions if set
    if only_ext:
        only_ext = _validate_extensions(only_ext)
    if except_ext:
        except_ext = _validate_extensions(except_ext)

    return {
        CONF_PATTERN: pattern,
        CONF_ONLY_EXTENSIONS: only_ext,
        CONF_EXCEPT_EXTENSIONS: except_ext,
    }


class RetentionCleanerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Retention Cleaner."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                base_path = _validate_base_path(user_input[CONF_BASE_PATH])
                run_at = _validate_run_at(user_input.get(CONF_RUN_AT, DEFAULT_RUN_AT))

                # Validate pattern and extensions (mutual exclusion)
                validated = _validate_pattern_and_extensions(user_input)

                retention_days = int(
                    user_input.get(CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS)
                )
                if retention_days < 0:
                    raise vol.Invalid("retention_days_negative")
                if retention_days > 3650:  # 10 years maximum
                    raise vol.Invalid("retention_days_too_large")

                max_deletes = int(user_input.get(CONF_MAX_DELETES, DEFAULT_MAX_DELETES))
                keep_minimum_files = _validate_keep_minimum_files(
                    int(
                        user_input.get(
                            CONF_KEEP_MINIMUM_FILES, DEFAULT_KEEP_MINIMUM_FILES
                        )
                    ),
                    max_deletes,
                )
                max_files_in_folder = _validate_max_files_in_folder(
                    int(
                        user_input.get(
                            CONF_MAX_FILES_IN_FOLDER, DEFAULT_MAX_FILES_IN_FOLDER
                        )
                    ),
                    keep_minimum_files,
                )

                data = {
                    CONF_BASE_PATH: base_path,
                    CONF_PATTERN: validated[CONF_PATTERN],
                    CONF_ONLY_EXTENSIONS: validated[CONF_ONLY_EXTENSIONS],
                    CONF_EXCEPT_EXTENSIONS: validated[CONF_EXCEPT_EXTENSIONS],
                    CONF_RETENTION_DAYS: retention_days,
                    CONF_RUN_AT: run_at,
                    CONF_DRY_RUN: bool(user_input.get(CONF_DRY_RUN, DEFAULT_DRY_RUN)),
                    CONF_MAX_DELETES: max_deletes,
                    CONF_KEEP_MINIMUM_FILES: keep_minimum_files,
                    CONF_MAX_FILES_IN_FOLDER: max_files_in_folder,
                    CONF_REMOVE_EMPTY_FOLDERS: bool(
                        user_input.get(
                            CONF_REMOVE_EMPTY_FOLDERS, DEFAULT_REMOVE_EMPTY_FOLDERS
                        )
                    ),
                }

                title = base_path.split("/")[-1] or base_path
                _LOGGER.info(
                    "Creating config entry for path: %s (pattern: %s, only_ext: %s, except_ext: %s, retention: %d days)",
                    base_path,
                    data[CONF_PATTERN],
                    data[CONF_ONLY_EXTENSIONS],
                    data[CONF_EXCEPT_EXTENSIONS],
                    data[CONF_RETENTION_DAYS],
                )
                return self.async_create_entry(title=title, data=data)

            except vol.Invalid as e:
                # Map validation codes to correct field errors
                error_key = str(e)
                errors.update(_map_validation_error_to_fields(error_key))
                # Only log if it's an unknown error
                if error_key not in (
                    "base_path_not_media",
                    "run_at_invalid",
                    "pattern_too_broad",
                    "pattern_invalid_syntax",
                    "retention_days_negative",
                    "retention_days_too_large",
                    "keep_minimum_negative",
                    "keep_minimum_too_large",
                    "max_files_negative",
                    "max_files_too_large",
                    "extension_must_start_with_dot",
                    "extension_no_wildcards",
                    "extension_no_paths",
                    "extension_too_short",
                    "must_set_pattern_or_extensions",
                    "cannot_combine_pattern_and_extensions",
                    "cannot_use_both_only_and_except",
                ):
                    _LOGGER.error("Unexpected validation error: %s", error_key)

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_PATH): str,
                vol.Optional(CONF_PATTERN, default=DEFAULT_PATTERN): str,
                vol.Optional(CONF_ONLY_EXTENSIONS, default=""): str,
                vol.Optional(CONF_EXCEPT_EXTENSIONS, default=""): str,
                vol.Optional(
                    CONF_RETENTION_DAYS, default=DEFAULT_RETENTION_DAYS
                ): vol.Coerce(int),
                vol.Optional(CONF_RUN_AT, default=DEFAULT_RUN_AT): str,
                vol.Optional(CONF_DRY_RUN, default=DEFAULT_DRY_RUN): bool,
                vol.Optional(CONF_MAX_DELETES, default=DEFAULT_MAX_DELETES): vol.Coerce(
                    int
                ),
                vol.Optional(
                    CONF_KEEP_MINIMUM_FILES, default=DEFAULT_KEEP_MINIMUM_FILES
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_MAX_FILES_IN_FOLDER, default=DEFAULT_MAX_FILES_IN_FOLDER
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_REMOVE_EMPTY_FOLDERS, default=DEFAULT_REMOVE_EMPTY_FOLDERS
                ): bool,
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
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors: dict[str, str] = {}

        current = {**self._config_entry.data, **self._config_entry.options}

        if user_input is not None:
            try:
                base_path = _validate_base_path(user_input[CONF_BASE_PATH])
                run_at = _validate_run_at(user_input.get(CONF_RUN_AT, DEFAULT_RUN_AT))

                # Validate pattern and extensions (mutual exclusion)
                validated = _validate_pattern_and_extensions(user_input)

                retention_days = int(
                    user_input.get(CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS)
                )
                if retention_days < 0:
                    raise vol.Invalid("retention_days_negative")
                if retention_days > 3650:  # 10 years maximum
                    raise vol.Invalid("retention_days_too_large")

                max_deletes = int(user_input.get(CONF_MAX_DELETES, DEFAULT_MAX_DELETES))
                keep_minimum_files = _validate_keep_minimum_files(
                    int(
                        user_input.get(
                            CONF_KEEP_MINIMUM_FILES, DEFAULT_KEEP_MINIMUM_FILES
                        )
                    ),
                    max_deletes,
                )
                max_files_in_folder = _validate_max_files_in_folder(
                    int(
                        user_input.get(
                            CONF_MAX_FILES_IN_FOLDER, DEFAULT_MAX_FILES_IN_FOLDER
                        )
                    ),
                    keep_minimum_files,
                )

                _LOGGER.info(
                    "Updating config for path: %s (pattern: %s, only_ext: %s, except_ext: %s, retention: %d days)",
                    base_path,
                    validated[CONF_PATTERN],
                    validated[CONF_ONLY_EXTENSIONS],
                    validated[CONF_EXCEPT_EXTENSIONS],
                    retention_days,
                )
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_BASE_PATH: base_path,
                        CONF_PATTERN: validated[CONF_PATTERN],
                        CONF_ONLY_EXTENSIONS: validated[CONF_ONLY_EXTENSIONS],
                        CONF_EXCEPT_EXTENSIONS: validated[CONF_EXCEPT_EXTENSIONS],
                        CONF_RETENTION_DAYS: retention_days,
                        CONF_RUN_AT: run_at,
                        CONF_DRY_RUN: bool(
                            user_input.get(CONF_DRY_RUN, DEFAULT_DRY_RUN)
                        ),
                        CONF_MAX_DELETES: max_deletes,
                        CONF_KEEP_MINIMUM_FILES: keep_minimum_files,
                        CONF_MAX_FILES_IN_FOLDER: max_files_in_folder,
                        CONF_REMOVE_EMPTY_FOLDERS: bool(
                            user_input.get(
                                CONF_REMOVE_EMPTY_FOLDERS, DEFAULT_REMOVE_EMPTY_FOLDERS
                            )
                        ),
                    },
                )

            except vol.Invalid as e:
                error_key = str(e)
                errors.update(_map_validation_error_to_fields(error_key))
                # Only log if it's an unknown error
                if error_key not in (
                    "base_path_not_media",
                    "run_at_invalid",
                    "pattern_too_broad",
                    "pattern_invalid_syntax",
                    "retention_days_negative",
                    "retention_days_too_large",
                    "keep_minimum_negative",
                    "keep_minimum_too_large",
                    "max_files_negative",
                    "max_files_too_large",
                    "extension_must_start_with_dot",
                    "extension_no_wildcards",
                    "extension_no_paths",
                    "extension_too_short",
                    "must_set_pattern_or_extensions",
                    "cannot_combine_pattern_and_extensions",
                    "cannot_use_both_only_and_except",
                ):
                    _LOGGER.error(
                        "Unexpected validation error in options flow: %s", error_key
                    )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_BASE_PATH, default=current.get(CONF_BASE_PATH, "")
                ): str,
                vol.Optional(
                    CONF_PATTERN, default=current.get(CONF_PATTERN, DEFAULT_PATTERN)
                ): str,
                vol.Optional(
                    CONF_ONLY_EXTENSIONS, default=current.get(CONF_ONLY_EXTENSIONS, "")
                ): str,
                vol.Optional(
                    CONF_EXCEPT_EXTENSIONS,
                    default=current.get(CONF_EXCEPT_EXTENSIONS, ""),
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
                vol.Optional(
                    CONF_KEEP_MINIMUM_FILES,
                    default=current.get(
                        CONF_KEEP_MINIMUM_FILES, DEFAULT_KEEP_MINIMUM_FILES
                    ),
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_MAX_FILES_IN_FOLDER,
                    default=current.get(
                        CONF_MAX_FILES_IN_FOLDER, DEFAULT_MAX_FILES_IN_FOLDER
                    ),
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_REMOVE_EMPTY_FOLDERS,
                    default=current.get(
                        CONF_REMOVE_EMPTY_FOLDERS, DEFAULT_REMOVE_EMPTY_FOLDERS
                    ),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
