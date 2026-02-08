"""Test retention_cleaner text entities."""

from unittest.mock import patch

from homeassistant.components.text import (
    ATTR_VALUE,
    DOMAIN as TEXT_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.retention_cleaner.const import (
    CONF_EXCEPT_EXTENSIONS,
    CONF_ONLY_EXTENSIONS,
    CONF_PATTERN,
    DOMAIN,
)
from tests.conftest import (
    TEST_DANGEROUS_PATTERN_ALL,
    TEST_DANGEROUS_PATTERN_STAR,
    TEST_EXTENSION_NO_DOT,
    TEST_EXTENSION_WITH_PATH,
    TEST_EXTENSION_WITH_WILDCARD,
    TEST_VALID_EXTENSIONS_EXCEPT,
    TEST_VALID_EXTENSIONS_ONLY,
    TEST_VALID_PATTERN,
)


async def test_text_entity_setup(hass: HomeAssistant, init_integration):
    """Test all 3 text entities are created during platform setup."""
    state = hass.states.get("text.test_cleanup_pattern")
    assert state is not None, "pattern text entity should exist"

    state = hass.states.get("text.test_cleanup_only_extensions")
    assert state is not None, "only_extensions text entity should exist"

    state = hass.states.get("text.test_cleanup_except_extensions")
    assert state is not None, "except_extensions text entity should exist"


async def test_text_entity_initial_values(hass: HomeAssistant, init_integration):
    """Test initial values match coordinator config."""
    coordinator = init_integration.runtime_data

    state = hass.states.get("text.test_cleanup_pattern")
    assert state is not None, "pattern text entity should exist"
    assert (
        state.state == coordinator.pattern
    ), "Initial pattern should match coordinator"

    state = hass.states.get("text.test_cleanup_only_extensions")
    assert state is not None, "only_extensions text entity should exist"
    assert (
        state.state == coordinator.only_extensions
    ), "Initial only_extensions should match coordinator"

    state = hass.states.get("text.test_cleanup_except_extensions")
    assert state is not None, "except_extensions text entity should exist"
    assert (
        state.state == coordinator.except_extensions
    ), "Initial except_extensions should match coordinator"


async def test_text_entity_set_pattern(hass: HomeAssistant, init_integration):
    """Test pattern text entity can be set."""
    await hass.services.async_call(
        TEXT_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "text.test_cleanup_pattern",
            ATTR_VALUE: TEST_VALID_PATTERN,
        },
        blocking=True,
    )

    state = hass.states.get("text.test_cleanup_pattern")
    assert state is not None, "Text entity should still exist"
    assert state.state == TEST_VALID_PATTERN, "State should be updated to new pattern"


async def test_text_entity_set_extensions(hass: HomeAssistant, mock_extension_config):
    """Test extension text entities can be set."""
    mock_extension_config.add_to_hass(hass)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
    ):
        assert await hass.config_entries.async_setup(mock_extension_config.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        TEXT_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "text.test_extension_mode_only_extensions",
            ATTR_VALUE: TEST_VALID_EXTENSIONS_ONLY,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("text.test_extension_mode_only_extensions")
    assert state is not None, "Text entity should still exist"
    assert (
        state.state == TEST_VALID_EXTENSIONS_ONLY
    ), "State should be updated to new extensions"


async def test_text_entity_set_value_updates_config(
    hass: HomeAssistant, init_integration
):
    """Test config is persisted via async_update_config_value."""
    coordinator = init_integration.runtime_data

    with (
        patch.object(coordinator, "async_update_config_value") as mock_update_config,
        patch.object(hass.config_entries, "async_update_entry"),
    ):
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "text.test_cleanup_pattern",
                ATTR_VALUE: "**/*.mp4",
            },
            blocking=True,
        )

        mock_update_config.assert_called_once_with(CONF_PATTERN, "**/*.mp4")


async def test_text_entity_set_value_triggers_scan(
    hass: HomeAssistant, init_integration
):
    """Test coordinator refresh is triggered."""
    coordinator = init_integration.runtime_data

    initial_last_scan = coordinator.last_scan

    with patch.object(hass.config_entries, "async_update_entry"):
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "text.test_cleanup_pattern",
                ATTR_VALUE: "**/*.txt",
            },
            blocking=True,
        )

    assert (
        coordinator.last_scan != initial_last_scan
    ), "Coordinator should have refreshed"


@pytest.mark.parametrize(
    "dangerous_pattern",
    [TEST_DANGEROUS_PATTERN_STAR, TEST_DANGEROUS_PATTERN_ALL],
)
async def test_text_entity_validation_rejects_dangerous_pattern(
    hass: HomeAssistant, init_integration, dangerous_pattern
):
    """Test pattern validation rejects dangerous patterns."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "text.test_cleanup_pattern",
                ATTR_VALUE: dangerous_pattern,
            },
            blocking=True,
        )

    error_msg = str(exc_info.value).lower()
    assert (
        "pattern_too_broad" in error_msg
        or "too broad" in error_msg
        or "broad" in error_msg
    ), f"Should reject dangerous pattern: {dangerous_pattern}"


@pytest.mark.parametrize(
    ("entity_id", "invalid_value", "expected_error"),
    [
        (
            "text.test_cleanup_only_extensions",
            TEST_EXTENSION_NO_DOT,
            "extension_must_start_with_dot",
        ),
        (
            "text.test_cleanup_except_extensions",
            TEST_EXTENSION_NO_DOT,
            "extension_must_start_with_dot",
        ),
    ],
)
async def test_text_entity_validation_requires_dot(
    hass: HomeAssistant, init_integration, entity_id, invalid_value, expected_error
):
    """Test extensions must start with dot."""
    hass.config_entries.async_update_entry(
        init_integration,
        options={
            CONF_PATTERN: "",
            CONF_ONLY_EXTENSIONS: "",
            CONF_EXCEPT_EXTENSIONS: "",
        },
    )
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: invalid_value},
            blocking=True,
        )

    error_msg = str(exc_info.value).lower()
    assert (
        expected_error.lower() in error_msg
        or "dot" in error_msg
        or "start with" in error_msg
    ), f"Should require dot for extension: {invalid_value}"


async def test_text_entity_mutual_exclusion_pattern_extensions(
    hass: HomeAssistant, init_integration
):
    """Test cannot set both pattern and extensions."""
    hass.config_entries.async_update_entry(
        init_integration,
        options={
            CONF_PATTERN: TEST_VALID_PATTERN,
            CONF_ONLY_EXTENSIONS: "",
            CONF_EXCEPT_EXTENSIONS: "",
        },
    )
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "text.test_cleanup_only_extensions",
                ATTR_VALUE: TEST_VALID_EXTENSIONS_ONLY,
            },
            blocking=True,
        )

    error_msg = str(exc_info.value).lower()
    assert (
        "cannot_combine_pattern_and_extensions" in error_msg
        or "cannot" in error_msg
        or "pattern" in error_msg
        or "extension" in error_msg
    ), "Should reject setting extensions when pattern is set"

    hass.config_entries.async_update_entry(
        init_integration,
        options={
            CONF_PATTERN: "",
            CONF_ONLY_EXTENSIONS: TEST_VALID_EXTENSIONS_ONLY,
            CONF_EXCEPT_EXTENSIONS: "",
        },
    )
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "text.test_cleanup_pattern",
                ATTR_VALUE: TEST_VALID_PATTERN,
            },
            blocking=True,
        )

    error_msg = str(exc_info.value).lower()
    assert (
        "cannot_combine_pattern_and_extensions" in error_msg
        or "cannot" in error_msg
        or "pattern" in error_msg
        or "extension" in error_msg
    ), "Should reject setting pattern when extensions are set"


@pytest.mark.parametrize(
    ("entity_id", "wildcard_value"),
    [
        ("text.test_cleanup_only_extensions", TEST_EXTENSION_WITH_WILDCARD),
        ("text.test_cleanup_except_extensions", TEST_EXTENSION_WITH_WILDCARD),
        ("text.test_cleanup_only_extensions", ".test?"),
        ("text.test_cleanup_except_extensions", ".file[0-9]"),
    ],
)
async def test_text_entity_no_wildcards_in_extensions(
    hass: HomeAssistant, init_integration, entity_id, wildcard_value
):
    """Test extensions cannot contain wildcards."""
    hass.config_entries.async_update_entry(
        init_integration,
        options={
            CONF_PATTERN: "",
            CONF_ONLY_EXTENSIONS: "",
            CONF_EXCEPT_EXTENSIONS: "",
        },
    )
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: wildcard_value},
            blocking=True,
        )

    error_msg = str(exc_info.value).lower()
    assert (
        "extension_no_wildcards" in error_msg
        or "wildcard" in error_msg
        or "not allowed" in error_msg
    ), f"Should reject wildcard in extension: {wildcard_value}"


async def test_text_entity_attributes(hass: HomeAssistant, init_integration):
    """Test text entity attributes and configuration."""
    registry = er.async_get(hass)

    for key, entity_suffix in [
        (CONF_PATTERN, "pattern"),
        (CONF_ONLY_EXTENSIONS, "only_extensions"),
        (CONF_EXCEPT_EXTENSIONS, "except_extensions"),
    ]:
        entity_id = f"text.test_cleanup_{entity_suffix}"
        entry = registry.async_get(entity_id)
        assert entry is not None, f"{key} text entity should exist in registry"
        assert (
            entry.unique_id == f"{init_integration.entry_id}_{key}"
        ), f"Should have correct unique_id format for {key}"
        assert (
            entry.entity_category == EntityCategory.CONFIG
        ), f"Should have CONFIG entity category for {key}"

        state = hass.states.get(entity_id)
        assert state is not None, f"{key} text entity state should exist"
        assert (
            state.attributes.get("mode") == "text"
        ), f"Should have 'text' mode for {key}"
        assert (
            state.attributes.get("max") == 255
        ), f"Should have max length 255 for {key}"


async def test_text_entity_device_info(hass: HomeAssistant, init_integration):
    """Test that text entities are linked to the correct device."""
    registry = er.async_get(hass)

    entry = registry.async_get("text.test_cleanup_pattern")
    assert entry is not None, "Pattern text entity should exist"
    assert entry.device_id is not None, "Should be linked to device"

    try:
        device_registry = hass.helpers.device_registry.async_get()
    except TypeError:
        device_registry = hass.helpers.device_registry.async_get(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, init_integration.entry_id)}
    )
    assert device is not None, "Device should exist"
    assert device.name == "Test Cleanup", "Device should have correct name"
    assert device.model == "Folder retention rule", "Device should have correct model"
    assert (
        device.manufacturer == "Retention Cleaner"
    ), "Device should have correct manufacturer"


async def test_text_entity_unique_id_stable(hass: HomeAssistant, init_integration):
    """Test that text entity unique IDs remain stable."""
    registry = er.async_get(hass)
    entry_id = init_integration.entry_id

    for key in [CONF_PATTERN, CONF_ONLY_EXTENSIONS, CONF_EXCEPT_EXTENSIONS]:
        entity_id = registry.async_get_entity_id(
            TEXT_DOMAIN, DOMAIN, f"{entry_id}_{key}"
        )
        assert entity_id is not None, f"{key} text entity should be found by unique_id"


async def test_text_entity_updates_from_coordinator(
    hass: HomeAssistant, init_integration
):
    """Test that text entities reflect coordinator config changes."""
    coordinator = init_integration.runtime_data

    await coordinator.async_update_config_value(CONF_PATTERN, "**/*.png")
    await hass.async_block_till_done()

    state = hass.states.get("text.test_cleanup_pattern")
    assert state is not None, "Text entity should still exist"
    assert state.state == "**/*.png", "State should reflect updated coordinator config"


async def test_text_entity_empty_pattern_allowed_with_extensions(
    hass: HomeAssistant, init_integration
):
    """Test empty pattern is allowed when extensions are set."""
    hass.config_entries.async_update_entry(
        init_integration,
        options={
            CONF_PATTERN: "",
            CONF_ONLY_EXTENSIONS: TEST_VALID_EXTENSIONS_ONLY,
            CONF_EXCEPT_EXTENSIONS: "",
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        TEXT_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "text.test_cleanup_pattern", ATTR_VALUE: ""},
        blocking=True,
    )

    state = hass.states.get("text.test_cleanup_pattern")
    assert state is not None, "Text entity should still exist"
    assert state.state == "", "Empty pattern should be allowed with extensions"


async def test_text_entity_empty_extensions_allowed(
    hass: HomeAssistant, init_integration
):
    """Test empty extensions are allowed."""
    hass.config_entries.async_update_entry(
        init_integration,
        options={
            CONF_PATTERN: TEST_VALID_PATTERN,
            CONF_ONLY_EXTENSIONS: "",
            CONF_EXCEPT_EXTENSIONS: "",
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        TEXT_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "text.test_cleanup_only_extensions", ATTR_VALUE: ""},
        blocking=True,
    )

    state = hass.states.get("text.test_cleanup_only_extensions")
    assert state is not None, "Text entity should still exist"
    assert state.state == "", "Empty extensions should be allowed"


async def test_text_entity_cannot_use_both_only_and_except(
    hass: HomeAssistant, init_integration
):
    """Test cannot use both only_extensions and except_extensions."""
    hass.config_entries.async_update_entry(
        init_integration,
        options={
            CONF_PATTERN: "",
            CONF_ONLY_EXTENSIONS: TEST_VALID_EXTENSIONS_ONLY,
            CONF_EXCEPT_EXTENSIONS: "",
        },
    )
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "text.test_cleanup_except_extensions",
                ATTR_VALUE: TEST_VALID_EXTENSIONS_EXCEPT,
            },
            blocking=True,
        )

    error_msg = str(exc_info.value).lower()
    assert (
        "cannot_use_both_only_and_except" in error_msg
        or "both" in error_msg
        or "exclusive" in error_msg
    ), "Should reject setting except_extensions when only_extensions is set"


async def test_text_entity_invalid_pattern_syntax(
    hass: HomeAssistant, init_integration
):
    """Test pattern validation rejects invalid syntax."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "text.test_cleanup_pattern", ATTR_VALUE: "***"},
            blocking=True,
        )

    error_msg = str(exc_info.value).lower()
    assert (
        "pattern_invalid_syntax" in error_msg
        or "invalid" in error_msg
        or "syntax" in error_msg
    ), "Should reject invalid pattern syntax"


async def test_text_entity_extension_no_path_separators(
    hass: HomeAssistant, init_integration
):
    """Test extensions cannot contain path separators."""
    hass.config_entries.async_update_entry(
        init_integration,
        options={
            CONF_PATTERN: "",
            CONF_ONLY_EXTENSIONS: "",
            CONF_EXCEPT_EXTENSIONS: "",
        },
    )
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "text.test_cleanup_only_extensions",
                ATTR_VALUE: TEST_EXTENSION_WITH_PATH,
            },
            blocking=True,
        )

    error_msg = str(exc_info.value).lower()
    assert (
        "extension_no_paths" in error_msg
        or "path" in error_msg
        or "separator" in error_msg
    ), "Should reject path separators in extensions"


async def test_text_entity_multiple_extensions_validation(
    hass: HomeAssistant, init_integration
):
    """Test validation works with multiple comma-separated extensions."""
    hass.config_entries.async_update_entry(
        init_integration,
        options={
            CONF_PATTERN: "",
            CONF_ONLY_EXTENSIONS: "",
            CONF_EXCEPT_EXTENSIONS: "",
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        TEXT_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "text.test_cleanup_only_extensions",
            ATTR_VALUE: ".mp4,.jpg,.png,.gif",
        },
        blocking=True,
    )

    state = hass.states.get("text.test_cleanup_only_extensions")
    assert state is not None, "Text entity should exist"
    assert (
        ".mp4" in state.state and ".jpg" in state.state
    ), "Should accept multiple valid extensions"


async def test_text_entity_extension_too_short(hass: HomeAssistant, init_integration):
    """Test extensions must have at least one character after dot."""
    hass.config_entries.async_update_entry(
        init_integration,
        options={
            CONF_PATTERN: "",
            CONF_ONLY_EXTENSIONS: "",
            CONF_EXCEPT_EXTENSIONS: "",
        },
    )
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "text.test_cleanup_only_extensions", ATTR_VALUE: "."},
            blocking=True,
        )

    error_msg = str(exc_info.value).lower()
    assert (
        "extension_too_short" in error_msg
        or "too short" in error_msg
        or "short" in error_msg
    ), "Should reject extension with no characters after dot"


async def test_text_entity_availability(hass: HomeAssistant, init_integration):
    """Test text entity availability based on coordinator."""
    coordinator = init_integration.runtime_data

    state = hass.states.get("text.test_cleanup_pattern")
    assert state.state != "unavailable", "Should be available when coordinator is ready"

    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    state = hass.states.get("text.test_cleanup_pattern")
    assert (
        state.state != "unavailable"
    ), "Text entity should remain available even with no coordinator data"


async def test_only_extensions_rejects_except_extensions_explicit(
    hass: HomeAssistant, init_integration
):
    """Test only_extensions rejects except_extensions when already set."""
    hass.config_entries.async_update_entry(
        init_integration,
        options={
            CONF_PATTERN: "",
            CONF_ONLY_EXTENSIONS: TEST_VALID_EXTENSIONS_ONLY,
            CONF_EXCEPT_EXTENSIONS: "",
        },
    )
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "text.test_cleanup_except_extensions",
                ATTR_VALUE: TEST_VALID_EXTENSIONS_EXCEPT,
            },
            blocking=True,
        )

    error_msg = str(exc_info.value).lower()
    assert (
        "cannot_use_both_only_and_except" in error_msg
        or "both" in error_msg
        or "exclusive" in error_msg
    ), "Should reject except_extensions when only_extensions is set"


async def test_except_extensions_rejects_pattern_explicit(
    hass: HomeAssistant, init_integration
):
    """Test except_extensions rejects pattern when pattern is set."""
    hass.config_entries.async_update_entry(
        init_integration,
        options={
            CONF_PATTERN: TEST_VALID_PATTERN,
            CONF_ONLY_EXTENSIONS: "",
            CONF_EXCEPT_EXTENSIONS: "",
        },
    )
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "text.test_cleanup_except_extensions",
                ATTR_VALUE: TEST_VALID_EXTENSIONS_EXCEPT,
            },
            blocking=True,
        )

    error_msg = str(exc_info.value).lower()
    assert (
        "cannot_combine_pattern_and_extensions" in error_msg
        or "cannot" in error_msg
        or "pattern" in error_msg
    ), "Should reject except_extensions when pattern is set"


async def test_except_extensions_rejects_only_extensions_explicit(
    hass: HomeAssistant, init_integration
):
    """Test except_extensions rejects only_extensions when already set."""
    hass.config_entries.async_update_entry(
        init_integration,
        options={
            CONF_PATTERN: "",
            CONF_ONLY_EXTENSIONS: TEST_VALID_EXTENSIONS_ONLY,
            CONF_EXCEPT_EXTENSIONS: "",
        },
    )
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "text.test_cleanup_except_extensions",
                ATTR_VALUE: TEST_VALID_EXTENSIONS_EXCEPT,
            },
            blocking=True,
        )

    error_msg = str(exc_info.value).lower()
    assert (
        "cannot_use_both_only_and_except" in error_msg
        or "both" in error_msg
        or "exclusive" in error_msg
    ), "Should reject except_extensions when only_extensions is set"


async def test_only_extensions_rejects_when_except_extensions_set(
    hass: HomeAssistant, init_integration
):
    """Test only_extensions rejects when except_extensions is already set."""
    hass.config_entries.async_update_entry(
        init_integration,
        options={
            CONF_PATTERN: "",
            CONF_ONLY_EXTENSIONS: "",
            CONF_EXCEPT_EXTENSIONS: TEST_VALID_EXTENSIONS_EXCEPT,
        },
    )
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "text.test_cleanup_only_extensions",
                ATTR_VALUE: TEST_VALID_EXTENSIONS_ONLY,
            },
            blocking=True,
        )

    error_msg = str(exc_info.value).lower()
    assert (
        "cannot_use_both_only_and_except" in error_msg
        or "both" in error_msg
        or "exclusive" in error_msg
    ), "Should reject only_extensions when except_extensions is set"


async def test_except_extensions_allows_empty_value(
    hass: HomeAssistant, init_integration
):
    """Test except_extensions allows empty value to clear filter."""
    hass.config_entries.async_update_entry(
        init_integration,
        options={
            CONF_PATTERN: TEST_VALID_PATTERN,
            CONF_ONLY_EXTENSIONS: "",
            CONF_EXCEPT_EXTENSIONS: TEST_VALID_EXTENSIONS_EXCEPT,
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        TEXT_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "text.test_cleanup_except_extensions",
            ATTR_VALUE: "",
        },
        blocking=True,
    )

    state = hass.states.get("text.test_cleanup_except_extensions")
    assert state is not None, "Text entity should exist"
    assert state.state == "", "Empty value should be allowed to clear filter"
