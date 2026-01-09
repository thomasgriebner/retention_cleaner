"""Test the retention_cleaner config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.retention_cleaner.const import (
    CONF_BASE_PATH,
    CONF_DRY_RUN,
    CONF_MAX_DELETES,
    CONF_PATTERN,
    CONF_RETENTION_DAYS,
    CONF_SCHEDULE_TIME,
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
                CONF_NAME: "Test Cleanup",
                CONF_BASE_PATH: "/media/test",
                CONF_PATTERN: "*.jpg",
                CONF_RETENTION_DAYS: 7,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: 100,
                CONF_SCHEDULE_TIME: "02:00",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Cleanup"
    assert result2["data"] == {
        CONF_BASE_PATH: "/media/test",
        CONF_PATTERN: "*.jpg",
        CONF_RETENTION_DAYS: 7,
        CONF_DRY_RUN: True,
        CONF_MAX_DELETES: 100,
        CONF_SCHEDULE_TIME: "02:00",
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
            CONF_NAME: "Test Cleanup",
            CONF_BASE_PATH: "/home/user/test",  # Invalid path
            CONF_PATTERN: "*.jpg",
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_SCHEDULE_TIME: "02:00",
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
            CONF_NAME: "Test Cleanup",
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*",  # Dangerous pattern
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_SCHEDULE_TIME: "02:00",
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
            CONF_NAME: "Test Cleanup",
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "***test.jpg",  # Invalid syntax
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_SCHEDULE_TIME: "02:00",
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
            CONF_NAME: "Test Cleanup",
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*.jpg",
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_SCHEDULE_TIME: "25:00",  # Invalid hour
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_SCHEDULE_TIME: "schedule_time_invalid"}


async def test_form_negative_retention_days(hass: HomeAssistant) -> None:
    """Test validation error for negative retention days."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Cleanup",
            CONF_BASE_PATH: "/media/test",
            CONF_PATTERN: "*.jpg",
            CONF_RETENTION_DAYS: -1,  # Negative value
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_SCHEDULE_TIME: "02:00",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_RETENTION_DAYS: "retention_days_negative"}


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
            CONF_PATTERN: "*.log",
            CONF_RETENTION_DAYS: 14,
            CONF_DRY_RUN: False,
            CONF_MAX_DELETES: 200,
            CONF_SCHEDULE_TIME: "03:00",
        },
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_PATTERN: "*.log",
        CONF_RETENTION_DAYS: 14,
        CONF_DRY_RUN: False,
        CONF_MAX_DELETES: 200,
        CONF_SCHEDULE_TIME: "03:00",
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
                CONF_NAME: "Test Cleanup",
                CONF_BASE_PATH: "/media/test/",  # With trailing slash
                CONF_PATTERN: "*.jpg",
                CONF_RETENTION_DAYS: 7,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: 100,
                CONF_SCHEDULE_TIME: "02:00",
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
            CONF_NAME: "Another Cleanup",
            CONF_BASE_PATH: "/media/test",  # Same path as existing entry
            CONF_PATTERN: "*.png",
            CONF_RETENTION_DAYS: 7,
            CONF_DRY_RUN: True,
            CONF_MAX_DELETES: 100,
            CONF_SCHEDULE_TIME: "02:00",
        },
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
