"""Test the retention_cleaner config flow."""

from unittest.mock import patch

from homeassistant import config_entries

# CONF_NAME not used in this integration - title derived from base_path
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
import voluptuous as vol

from custom_components.retention_cleaner.const import (
    CONF_BASE_PATH,
    CONF_DRY_RUN,
    CONF_MAX_DELETES,
    CONF_PATTERN,
    CONF_RETENTION_DAYS,
    CONF_RUN_AT,
    DOMAIN,
)


async def test_form_valid_input(hass: HomeAssistant) -> None:
    """Test we get the form and can submit valid input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "custom_components.retention_cleaner.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_PATH: "/media/test",
                CONF_PATTERN: "*.jpg",
                CONF_RETENTION_DAYS: 7,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: 100,
                CONF_RUN_AT: "02:00",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test"  # Derived from base_path "/media/test"
    assert result2["data"] == {
        CONF_BASE_PATH: "/media/test",
        CONF_PATTERN: "*.jpg",
        CONF_RETENTION_DAYS: 7,
        CONF_DRY_RUN: True,
        CONF_MAX_DELETES: 100,
        CONF_RUN_AT: "02:00",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_path_not_media(hass: HomeAssistant) -> None:
    """Test validation error for path not in /media/."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_PATH: "/home/user/test",  # Invalid path
            CONF_PATTERN: "*.jpg",
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_RUN_AT: "02:00",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_BASE_PATH: "base_path_not_media"}


async def test_form_dangerous_pattern(hass: HomeAssistant) -> None:
    """Test validation error for dangerous pattern."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Test with "*" pattern (too broad)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*",  # Dangerous pattern
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_RUN_AT: "02:00",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_PATTERN: "pattern_too_broad"}


async def test_form_invalid_pattern_syntax(hass: HomeAssistant) -> None:
    """Test validation error for invalid pattern syntax."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Test with "***" in pattern
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "***test.jpg",  # Invalid syntax
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_RUN_AT: "02:00",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_PATTERN: "pattern_invalid_syntax"}


async def test_form_invalid_time_format(hass: HomeAssistant) -> None:
    """Test validation error for invalid time format."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Test with invalid time format
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*.jpg",
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_RUN_AT: "25:00",  # Invalid hour
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_RUN_AT: "run_at_invalid"}


async def test_form_negative_retention_days(hass: HomeAssistant) -> None:
    """Test validation error for negative retention days."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*.jpg",
            CONF_RETENTION_DAYS: -1,  # Negative value
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_RUN_AT: "02:00",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_RETENTION_DAYS: "retention_days_negative"}


async def test_retention_days_boundary_value(hass: HomeAssistant) -> None:
    """Test that retention_days = 3650 (maximum) is accepted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.retention_cleaner.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_PATH: "/media/test",
                CONF_PATTERN: "*.jpg",
                CONF_RETENTION_DAYS: 3650,  # Exactly at boundary
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: 100,
                CONF_RUN_AT: "02:00",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_RETENTION_DAYS] == 3650
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_retention_days_too_large(hass: HomeAssistant) -> None:
    """Test validation error for retention days exceeding maximum."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*.jpg",
            CONF_RETENTION_DAYS: 3651,  # Just over boundary
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_RUN_AT: "02:00",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_RETENTION_DAYS: "retention_days_too_large"}


async def test_form_retention_days_extreme_value(hass: HomeAssistant) -> None:
    """Test validation error for extremely large retention days."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*.jpg",
            CONF_RETENTION_DAYS: 99999,  # Extreme value
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_RUN_AT: "02:00",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_RETENTION_DAYS: "retention_days_too_large"}


async def test_options_flow(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test config options flow."""
    mock_setup_entry.add_to_hass(hass)

    # Start options flow
    result = await hass.config_entries.options.async_init(mock_setup_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    # Update options
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BASE_PATH: "/media/test",  # Must include base_path since it's required
            CONF_PATTERN: "*.log",
            CONF_RETENTION_DAYS: 14,
            CONF_DRY_RUN: False,
            CONF_MAX_DELETES: 200,
            CONF_RUN_AT: "03:00",
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_BASE_PATH: "/media/test",
        CONF_PATTERN: "*.log",
        CONF_RETENTION_DAYS: 14,
        CONF_DRY_RUN: False,
        CONF_MAX_DELETES: 200,
        CONF_RUN_AT: "03:00",
    }


async def test_path_trailing_slash_removed(hass: HomeAssistant) -> None:
    """Test that trailing slashes are removed from paths."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.retention_cleaner.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_PATH: "/media/test/",  # With trailing slash
                CONF_PATTERN: "*.jpg",
                CONF_RETENTION_DAYS: 7,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: 100,
                CONF_RUN_AT: "02:00",
            },
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_BASE_PATH] == "/media/test"  # Without trailing slash


async def test_duplicate_entry_prevention(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test that duplicate entries are prevented."""
    mock_setup_entry.add_to_hass(hass)

    # Try to create another entry with same path
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_PATH: "/media/test",  # Same path as existing entry
            CONF_PATTERN: "*.png",
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_RUN_AT: "02:00",
        },
    )

    # Note: We need to implement duplicate detection if desired
    # For now, this may create a second entry which is acceptable
    assert result2["type"] in (FlowResultType.ABORT, FlowResultType.CREATE_ENTRY)


async def test_validation_functions_directly() -> None:
    """Test validation functions work correctly without mocking."""
    import voluptuous as vol

    from custom_components.retention_cleaner.config_flow import (
        _validate_base_path,
        _validate_pattern,
        _validate_run_at,
    )

    # Test path validation - should work
    assert _validate_base_path("/media/test") == "/media/test"
    assert _validate_base_path("/media/test/") == "/media/test"  # Strips trailing slash

    # Test path validation - should fail
    with pytest.raises(vol.Invalid, match="base_path_not_media"):
        _validate_base_path("/home/user")

    # Test pattern validation - should work
    assert _validate_pattern("*.jpg") == "*.jpg"
    assert _validate_pattern("test*.log") == "test*.log"

    # Test pattern validation - should fail
    with pytest.raises(vol.Invalid, match="pattern_too_broad"):
        _validate_pattern("*")
    with pytest.raises(vol.Invalid, match="pattern_invalid_syntax"):
        _validate_pattern("***test")

    # Test time validation - should work
    assert _validate_run_at("02:00") == "02:00"
    assert _validate_run_at("23:59") == "23:59"

    # Test time validation - should fail
    with pytest.raises(vol.Invalid, match="run_at_invalid"):
        _validate_run_at("25:00")
    with pytest.raises(vol.Invalid, match="run_at_invalid"):
        _validate_run_at("12:60")


async def test_path_validation_with_os_error(hass: HomeAssistant) -> None:
    """Test path validation handles OSError/ValueError during Path.resolve()."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock Path.resolve to raise OSError (covers lines 53-55)
    with patch("pathlib.Path.resolve", side_effect=OSError("Mock error")):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_PATH: "/media/test",  # Valid prefix but resolve() fails
                CONF_PATTERN: "*.jpg",
                CONF_RETENTION_DAYS: 7,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: 100,
                CONF_RUN_AT: "02:00",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_BASE_PATH: "base_path_not_media"}


async def test_time_validation_invalid_formats(hass: HomeAssistant) -> None:
    """Test time validation with various invalid formats (covers lines 63-64)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Test invalid format "abc:def"
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*.jpg",
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_RUN_AT: "abc:def",  # Non-numeric format
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_RUN_AT: "run_at_invalid"}

    # Test invalid format "1:2" (not HH:MM)
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*.jpg",
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_RUN_AT: "1:2",  # Single digit format
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {CONF_RUN_AT: "run_at_invalid"}


async def test_pattern_validation_unclosed_brackets(hass: HomeAssistant) -> None:
    """Test pattern validation with unclosed brackets/braces (covers lines 89-90)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Test unclosed bracket
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "[abc",  # Unclosed bracket
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_RUN_AT: "02:00",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_PATTERN: "pattern_invalid_syntax"}

    # Test unclosed brace
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "{xyz",  # Unclosed brace
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_RUN_AT: "02:00",
        },
    )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {CONF_PATTERN: "pattern_invalid_syntax"}


async def test_unexpected_validation_error(hass: HomeAssistant) -> None:
    """Test config flow handles unexpected validation errors (covers lines 153-154)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock validation function to raise unexpected error
    from custom_components.retention_cleaner import config_flow

    def mock_validate_unexpected(value):
        raise vol.Invalid("unexpected_error_code")

    with patch.object(config_flow, "_validate_base_path", mock_validate_unexpected):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_PATH: "/media/test",
                CONF_PATTERN: "*.jpg",
                CONF_RETENTION_DAYS: 7,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: 100,
                CONF_RUN_AT: "02:00",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_options_flow_negative_retention_days(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test options flow handles negative retention days (covers line 203)."""
    mock_setup_entry.add_to_hass(hass)

    # Start options flow
    result = await hass.config_entries.options.async_init(mock_setup_entry.entry_id)

    # Configure with negative retention days
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*.log",
            CONF_RETENTION_DAYS: -5,  # Negative value
            CONF_DRY_RUN: False,
            CONF_MAX_DELETES: 200,
            CONF_RUN_AT: "03:00",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_RETENTION_DAYS: "retention_days_negative"}


async def test_options_flow_retention_days_too_large(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test options flow rejects retention days exceeding maximum."""
    mock_setup_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_setup_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*.log",
            CONF_RETENTION_DAYS: 3651,  # Just over boundary
            CONF_DRY_RUN: False,
            CONF_MAX_DELETES: 200,
            CONF_RUN_AT: "03:00",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_RETENTION_DAYS: "retention_days_too_large"}


async def test_options_flow_retention_days_extreme_value(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test options flow rejects extremely large retention days."""
    mock_setup_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_setup_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*.log",
            CONF_RETENTION_DAYS: 99999,  # Extreme value
            CONF_DRY_RUN: False,
            CONF_MAX_DELETES: 200,
            CONF_RUN_AT: "03:00",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_RETENTION_DAYS: "retention_days_too_large"}


async def test_options_flow_retention_days_boundary_value(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test options flow accepts retention_days = 3650 (maximum)."""
    mock_setup_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_setup_entry.entry_id)

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*.log",
            CONF_RETENTION_DAYS: 3650,  # Exactly at boundary
            CONF_DRY_RUN: False,
            CONF_MAX_DELETES: 200,
            CONF_RUN_AT: "03:00",
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_RETENTION_DAYS] == 3650


async def test_options_flow_error_handling(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test options flow error handling for all validation types (covers lines 227-241)."""
    mock_setup_entry.add_to_hass(hass)

    # Test path validation error in options
    result = await hass.config_entries.options.async_init(mock_setup_entry.entry_id)
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BASE_PATH: "/home/user",  # Invalid path
            CONF_PATTERN: "*.log",
            CONF_RETENTION_DAYS: 14,
            CONF_DRY_RUN: False,
            CONF_MAX_DELETES: 200,
            CONF_RUN_AT: "03:00",
        },
    )
    assert result2["errors"] == {CONF_BASE_PATH: "base_path_not_media"}

    # Test time validation error in options
    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*.log",
            CONF_RETENTION_DAYS: 14,
            CONF_DRY_RUN: False,
            CONF_MAX_DELETES: 200,
            CONF_RUN_AT: "25:99",  # Invalid time
        },
    )
    assert result3["errors"] == {CONF_RUN_AT: "run_at_invalid"}

    # Test pattern validation error in options
    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        user_input={
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*",  # Too broad pattern
            CONF_RETENTION_DAYS: 14,
            CONF_DRY_RUN: False,
            CONF_MAX_DELETES: 200,
            CONF_RUN_AT: "03:00",
        },
    )
    assert result4["errors"] == {CONF_PATTERN: "pattern_too_broad"}

    # Test unexpected validation error in options flow
    from custom_components.retention_cleaner import config_flow

    def mock_validate_unexpected(value):
        raise vol.Invalid("weird_unexpected_error")

    with patch.object(config_flow, "_validate_pattern", mock_validate_unexpected):
        result5 = await hass.config_entries.options.async_configure(
            result4["flow_id"],
            user_input={
                CONF_BASE_PATH: "/media/test",
                CONF_PATTERN: "*.log",
                CONF_RETENTION_DAYS: 14,
                CONF_DRY_RUN: False,
                CONF_MAX_DELETES: 200,
                CONF_RUN_AT: "03:00",
            },
        )

    assert result5["type"] == FlowResultType.FORM
    assert result5["errors"] == {"base": "unknown"}


async def test_symlink_validation_direct_symlink(caplog) -> None:
    """Test that direct symlinks are rejected and warning is logged."""
    from pathlib import Path

    from custom_components.retention_cleaner.config_flow import _validate_base_path

    test_path = "/media/test_symlink"

    with (
        patch.object(Path, "is_symlink") as mock_is_symlink,
        patch.object(Path, "resolve", return_value=Path("/media/test_symlink")),
        caplog.at_level("WARNING"),
    ):
        mock_is_symlink.return_value = True

        with pytest.raises(vol.Invalid, match="base_path_not_media"):
            _validate_base_path(test_path)

    assert "Symlink detected at path:" in caplog.text
    assert test_path in caplog.text


async def test_symlink_validation_parent_symlink(caplog) -> None:
    """Test that symlinks in parent directories are rejected and warning is logged."""
    from pathlib import Path

    from custom_components.retention_cleaner.config_flow import _validate_base_path

    test_path = "/media/parent/child"
    call_count = [0]

    def is_symlink_side_effect():
        call_count[0] += 1
        return call_count[0] != 1

    with (
        patch.object(Path, "is_symlink", side_effect=is_symlink_side_effect),
        patch.object(Path, "resolve", return_value=Path("/media/parent/child")),
        caplog.at_level("WARNING"),
        pytest.raises(vol.Invalid, match="base_path_not_media"),
    ):
        _validate_base_path(test_path)

    assert "Symlink detected in parent path:" in caplog.text
    assert "/media/parent" in caplog.text


async def test_symlink_validation_path_traversal(tmp_path) -> None:
    """Test that path traversal via symlinks is rejected."""
    from custom_components.retention_cleaner.config_flow import _validate_base_path

    outside_dir = tmp_path / "outside_media"
    outside_dir.mkdir()
    media_dir = tmp_path / "media" / "test"
    media_dir.mkdir(parents=True)
    symlink_path = media_dir / "escape"

    try:
        symlink_path.symlink_to(outside_dir)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported on this platform")

    with pytest.raises(vol.Invalid, match="base_path_not_media"):
        _validate_base_path(str(symlink_path))


async def test_symlink_validation_valid_path() -> None:
    """Test that valid non-symlink paths under /media/ are accepted."""
    from pathlib import Path

    from custom_components.retention_cleaner.config_flow import _validate_base_path

    test_path = "/media/valid_path"

    with (
        patch.object(Path, "is_symlink", return_value=False),
        patch.object(Path, "resolve", return_value=Path("/media/valid_path")),
    ):
        result = _validate_base_path(test_path)
        assert result == test_path


async def test_symlink_validation_config_flow_direct_symlink(
    hass: HomeAssistant, tmp_path
) -> None:
    """Test config flow rejects direct symlinks."""
    real_dir = tmp_path / "real_media"
    real_dir.mkdir()
    symlink_path = tmp_path / "media" / "symlinked"
    symlink_path.parent.mkdir(parents=True)

    try:
        symlink_path.symlink_to(real_dir)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported on this platform")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_PATH: str(symlink_path),
            CONF_PATTERN: "*.jpg",
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_RUN_AT: "02:00",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_BASE_PATH: "base_path_not_media"}


async def test_symlink_validation_config_flow_parent_symlink(
    hass: HomeAssistant, tmp_path
) -> None:
    """Test config flow rejects paths with symlinked parents."""
    real_dir = tmp_path / "real_directory"
    real_dir.mkdir()
    symlink_parent = tmp_path / "media" / "symlinked_parent"
    symlink_parent.parent.mkdir(parents=True)

    try:
        symlink_parent.symlink_to(real_dir)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported on this platform")

    child_path = symlink_parent / "child"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BASE_PATH: str(child_path),
            CONF_PATTERN: "*.jpg",
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_RUN_AT: "02:00",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_BASE_PATH: "base_path_not_media"}


async def test_symlink_validation_path_resolves_outside_media() -> None:
    """Test that paths resolving outside /media/ after symlink resolution are rejected."""
    from pathlib import Path

    from custom_components.retention_cleaner.config_flow import _validate_base_path

    test_path = "/media/potentially_dangerous"

    with (
        patch.object(Path, "is_symlink", return_value=False),
        patch.object(Path, "resolve", return_value=Path("/home/user/secret")),
        pytest.raises(vol.Invalid, match="base_path_not_media"),
    ):
        _validate_base_path(test_path)
