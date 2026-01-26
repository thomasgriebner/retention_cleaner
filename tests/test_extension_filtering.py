"""Test extension filtering feature for retention_cleaner."""

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.retention_cleaner.const import (
    CONF_BASE_PATH,
    CONF_DRY_RUN,
    CONF_EXCEPT_EXTENSIONS,
    CONF_MAX_DELETES,
    CONF_ONLY_EXTENSIONS,
    CONF_PATTERN,
    CONF_RETENTION_DAYS,
    CONF_RUN_AT,
    DEFAULT_PATTERN,
)
from custom_components.retention_cleaner.coordinator import (
    RetentionCleanerCoordinator,
    _cleanup_folder,
    _parse_extensions,
    _scan_folder,
)
from tests.conftest import (
    TEST_FILE_AGE_DAYS,
    TEST_MAX_DELETES,
    TEST_MEDIA_PATH,
    TEST_RETENTION_DAYS,
    TEST_RUN_AT,
)


class TestConfigFlowExtensionValidation:
    """Test config flow extension validation."""

    async def test_extension_validation_valid_formats(
        self, hass: HomeAssistant, extension_config_flow
    ) -> None:
        """Test extension validation accepts valid formats."""
        result = await extension_config_flow(
            {
                CONF_BASE_PATH: TEST_MEDIA_PATH,
                CONF_PATTERN: "",
                CONF_ONLY_EXTENSIONS: ".mp4,.jpg",
                CONF_RETENTION_DAYS: TEST_RETENTION_DAYS,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: TEST_MAX_DELETES,
                CONF_RUN_AT: TEST_RUN_AT,
            },
            expect_success=True,
        )

        assert (
            result["type"] == FlowResultType.CREATE_ENTRY
        ), "Should create entry with valid extensions"
        assert (
            result["data"][CONF_ONLY_EXTENSIONS] == ".mp4,.jpg"
        ), "Extensions should be preserved"
        assert (
            result["data"][CONF_PATTERN] == ""
        ), "Pattern should be empty in extension mode"

    async def test_extension_validation_with_spaces(
        self, hass: HomeAssistant, extension_config_flow
    ) -> None:
        """Test extension validation trims spaces correctly."""
        result = await extension_config_flow(
            {
                CONF_BASE_PATH: TEST_MEDIA_PATH,
                CONF_PATTERN: "",
                CONF_ONLY_EXTENSIONS: ".mp4, .jpg, .mkv",
                CONF_RETENTION_DAYS: TEST_RETENTION_DAYS,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: TEST_MAX_DELETES,
                CONF_RUN_AT: TEST_RUN_AT,
            },
            expect_success=True,
        )

        assert (
            result["type"] == FlowResultType.CREATE_ENTRY
        ), "Should accept extensions with spaces"

    async def test_extension_validation_empty_items_ignored(
        self, hass: HomeAssistant, extension_config_flow
    ) -> None:
        """Test extension validation ignores empty items from multiple commas."""
        result = await extension_config_flow(
            {
                CONF_BASE_PATH: TEST_MEDIA_PATH,
                CONF_PATTERN: "",
                CONF_ONLY_EXTENSIONS: ".mp4,,.jpg",
                CONF_RETENTION_DAYS: TEST_RETENTION_DAYS,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: TEST_MAX_DELETES,
                CONF_RUN_AT: TEST_RUN_AT,
            },
            expect_success=True,
        )

        assert (
            result["type"] == FlowResultType.CREATE_ENTRY
        ), "Should filter empty items from comma list"

    @pytest.mark.parametrize(
        "extension_input,expected_error",
        [
            ("mp4,jpg", "extension_must_start_with_dot"),
            (".mp*,.jpg", "extension_no_wildcards"),
            (".mp4/.jpg", "extension_no_paths"),
            (".", "extension_too_short"),
        ],
    )
    async def test_extension_validation_errors(
        self,
        hass: HomeAssistant,
        extension_config_flow,
        extension_input,
        expected_error,
    ) -> None:
        """Test extension validation rejects invalid formats."""
        result = await extension_config_flow(
            {
                CONF_BASE_PATH: TEST_MEDIA_PATH,
                CONF_PATTERN: "",
                CONF_ONLY_EXTENSIONS: extension_input,
                CONF_RETENTION_DAYS: TEST_RETENTION_DAYS,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: TEST_MAX_DELETES,
                CONF_RUN_AT: TEST_RUN_AT,
            }
        )

        assert (
            result["type"] == FlowResultType.FORM
        ), f"Should reject invalid extension: {extension_input}"
        assert (
            CONF_ONLY_EXTENSIONS in result["errors"]
        ), "Error should be on extension field"
        assert (
            result["errors"][CONF_ONLY_EXTENSIONS] == expected_error
        ), f"Should report {expected_error}"

    async def test_extension_validation_empty_string_input(
        self, hass: HomeAssistant, extension_config_flow
    ) -> None:
        """Test extension validation handles empty string correctly."""
        result = await extension_config_flow(
            {
                CONF_BASE_PATH: TEST_MEDIA_PATH,
                CONF_PATTERN: "**/*.jpg",
                CONF_ONLY_EXTENSIONS: "",
                CONF_EXCEPT_EXTENSIONS: "",
                CONF_RETENTION_DAYS: TEST_RETENTION_DAYS,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: TEST_MAX_DELETES,
                CONF_RUN_AT: TEST_RUN_AT,
            },
            expect_success=True,
        )

        assert (
            result["type"] == FlowResultType.CREATE_ENTRY
        ), "Should accept empty extensions with pattern"

    async def test_extension_validation_only_commas(
        self, hass: HomeAssistant, extension_config_flow
    ) -> None:
        """Test extension validation normalizes comma-only input to empty string."""
        result = await extension_config_flow(
            {
                CONF_BASE_PATH: TEST_MEDIA_PATH,
                CONF_PATTERN: "",
                CONF_ONLY_EXTENSIONS: ",,,",
                CONF_RETENTION_DAYS: TEST_RETENTION_DAYS,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: TEST_MAX_DELETES,
                CONF_RUN_AT: TEST_RUN_AT,
            },
            expect_success=True,
        )

        assert (
            result["type"] == FlowResultType.CREATE_ENTRY
        ), "Should normalize comma-only to empty"
        assert (
            result["data"][CONF_ONLY_EXTENSIONS] == ""
        ), "Only extensions should be empty"
        assert result["data"][CONF_PATTERN] == "", "Pattern should be empty"


class TestConfigFlowMutualExclusion:
    """Test mutual exclusion rules for pattern and extensions."""

    @pytest.mark.parametrize(
        "pattern,only_ext,except_ext,expected_error",
        [
            ("**/*.mp4", ".jpg", "", "cannot_combine_pattern_and_extensions"),
            ("", "", "", "must_set_pattern_or_extensions"),
            ("", ".mp4", ".log", "cannot_use_both_only_and_except"),
        ],
    )
    async def test_mutual_exclusion_errors(
        self,
        hass: HomeAssistant,
        extension_config_flow,
        pattern,
        only_ext,
        except_ext,
        expected_error,
    ) -> None:
        """Test mutual exclusion validation rules."""
        result = await extension_config_flow(
            {
                CONF_BASE_PATH: TEST_MEDIA_PATH,
                CONF_PATTERN: pattern,
                CONF_ONLY_EXTENSIONS: only_ext,
                CONF_EXCEPT_EXTENSIONS: except_ext,
                CONF_RETENTION_DAYS: TEST_RETENTION_DAYS,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: TEST_MAX_DELETES,
                CONF_RUN_AT: TEST_RUN_AT,
            }
        )

        assert result["type"] == FlowResultType.FORM, f"Should reject: {expected_error}"
        assert "base" in result["errors"], "Error should be on base field"
        assert (
            result["errors"]["base"] == expected_error
        ), f"Should report {expected_error}"

    async def test_pattern_mode_with_empty_extensions(
        self, hass: HomeAssistant, extension_config_flow
    ) -> None:
        """Test that pattern mode works when extensions are empty."""
        result = await extension_config_flow(
            {
                CONF_BASE_PATH: TEST_MEDIA_PATH,
                CONF_PATTERN: "**/*.mp4",
                CONF_ONLY_EXTENSIONS: "",
                CONF_EXCEPT_EXTENSIONS: "",
                CONF_RETENTION_DAYS: TEST_RETENTION_DAYS,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: TEST_MAX_DELETES,
                CONF_RUN_AT: TEST_RUN_AT,
            },
            expect_success=True,
        )

        assert (
            result["type"] == FlowResultType.CREATE_ENTRY
        ), "Should accept pattern mode"
        assert result["data"][CONF_PATTERN] == "**/*.mp4", "Pattern should be preserved"
        assert result["data"][CONF_ONLY_EXTENSIONS] == "", "Extensions should be empty"

    async def test_extension_mode_with_empty_pattern(
        self, hass: HomeAssistant, extension_config_flow
    ) -> None:
        """Test that extension mode works when pattern is empty."""
        result = await extension_config_flow(
            {
                CONF_BASE_PATH: TEST_MEDIA_PATH,
                CONF_PATTERN: "",
                CONF_ONLY_EXTENSIONS: ".mp4",
                CONF_RETENTION_DAYS: TEST_RETENTION_DAYS,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: TEST_MAX_DELETES,
                CONF_RUN_AT: TEST_RUN_AT,
            },
            expect_success=True,
        )

        assert (
            result["type"] == FlowResultType.CREATE_ENTRY
        ), "Should accept extension mode"
        assert result["data"][CONF_PATTERN] == "", "Pattern should be empty"
        assert (
            result["data"][CONF_ONLY_EXTENSIONS] == ".mp4"
        ), "Extension should be preserved"

    async def test_except_extensions_mode(
        self, hass: HomeAssistant, extension_config_flow
    ) -> None:
        """Test that except_extensions mode works correctly."""
        result = await extension_config_flow(
            {
                CONF_BASE_PATH: TEST_MEDIA_PATH,
                CONF_PATTERN: "",
                CONF_EXCEPT_EXTENSIONS: ".mkv,.log",
                CONF_RETENTION_DAYS: TEST_RETENTION_DAYS,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: TEST_MAX_DELETES,
                CONF_RUN_AT: TEST_RUN_AT,
            },
            expect_success=True,
        )

        assert (
            result["type"] == FlowResultType.CREATE_ENTRY
        ), "Should accept except_extensions mode"
        assert (
            result["data"][CONF_EXCEPT_EXTENSIONS] == ".mkv,.log"
        ), "Except extensions should be preserved"
        assert result["data"][CONF_PATTERN] == "", "Pattern should be empty"

    async def test_pattern_validation_empty_with_allow_empty(
        self, hass: HomeAssistant, extension_config_flow
    ) -> None:
        """Test pattern validation allows empty when allow_empty=True (extension mode)."""
        result = await extension_config_flow(
            {
                CONF_BASE_PATH: TEST_MEDIA_PATH,
                CONF_PATTERN: "",
                CONF_ONLY_EXTENSIONS: ".mp4",
                CONF_RETENTION_DAYS: TEST_RETENTION_DAYS,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: TEST_MAX_DELETES,
                CONF_RUN_AT: TEST_RUN_AT,
            },
            expect_success=True,
        )

        assert (
            result["type"] == FlowResultType.CREATE_ENTRY
        ), "Should allow empty pattern in extension mode"
        assert result["data"][CONF_PATTERN] == "", "Pattern should be empty"

    @pytest.mark.parametrize(
        "extension_field,extension_value",
        [
            (CONF_ONLY_EXTENSIONS, ".mp4,.mkv"),
            (CONF_EXCEPT_EXTENSIONS, ".log,.tmp"),
        ],
    )
    async def test_default_pattern_with_extensions_should_succeed(
        self,
        hass: HomeAssistant,
        extension_config_flow,
        extension_field,
        extension_value,
    ) -> None:
        """Test that DEFAULT_PATTERN is overridden when extensions are provided.

        Bug: Users get 'cannot_combine_pattern_and_extensions' error when they
        set extension filters with the default pattern value. The default should
        be treated as 'not set' to allow extension filters to work.
        """
        result = await extension_config_flow(
            {
                CONF_BASE_PATH: TEST_MEDIA_PATH,
                CONF_PATTERN: DEFAULT_PATTERN,
                extension_field: extension_value,
                CONF_RETENTION_DAYS: TEST_RETENTION_DAYS,
                CONF_DRY_RUN: True,
                CONF_MAX_DELETES: TEST_MAX_DELETES,
                CONF_RUN_AT: TEST_RUN_AT,
            }
        )

        assert (
            result["type"] == FlowResultType.CREATE_ENTRY
        ), f"Should allow extensions to override DEFAULT_PATTERN (got error: {result.get('errors', {})})"
        assert (
            result["data"][CONF_PATTERN] == ""
        ), "Pattern should be empty when extensions used"
        assert (
            result["data"][extension_field] == extension_value
        ), f"Extension filter should be set to {extension_value}"


class TestOptionsFlowExtensions:
    """Test options flow with extensions."""

    async def test_options_flow_extension_validation(
        self, hass: HomeAssistant, mock_setup_entry
    ) -> None:
        """Test options flow validates extensions correctly."""
        mock_setup_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(mock_setup_entry.entry_id)

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_BASE_PATH: TEST_MEDIA_PATH,
                CONF_PATTERN: "",
                CONF_ONLY_EXTENSIONS: ".mp4,.jpg",
                CONF_RETENTION_DAYS: 14,
                CONF_DRY_RUN: False,
                CONF_MAX_DELETES: 200,
                CONF_RUN_AT: "03:00",
            },
        )

        assert (
            result2["type"] == FlowResultType.CREATE_ENTRY
        ), "Should accept valid extensions in options flow"
        assert (
            result2["data"][CONF_ONLY_EXTENSIONS] == ".mp4,.jpg"
        ), "Extensions should be preserved"
        assert result2["data"][CONF_PATTERN] == "", "Pattern should be empty"

    async def test_options_flow_extension_mutual_exclusion_error(
        self, hass: HomeAssistant, mock_setup_entry
    ) -> None:
        """Test options flow rejects invalid extension combinations."""
        mock_setup_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(mock_setup_entry.entry_id)

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_BASE_PATH: TEST_MEDIA_PATH,
                CONF_PATTERN: "*.jpg",
                CONF_ONLY_EXTENSIONS: ".mp4",
                CONF_RETENTION_DAYS: 14,
                CONF_DRY_RUN: False,
                CONF_MAX_DELETES: 200,
                CONF_RUN_AT: "03:00",
            },
        )

        assert (
            result2["type"] == FlowResultType.FORM
        ), "Should reject pattern with extensions in options flow"
        assert "base" in result2["errors"], "Error should be on base field"
        assert (
            result2["errors"]["base"] == "cannot_combine_pattern_and_extensions"
        ), "Should report mutual exclusion error"

    async def test_options_flow_extension_validation_errors(
        self, hass: HomeAssistant, mock_setup_entry
    ) -> None:
        """Test options flow extension validation error mapping."""
        mock_setup_entry.add_to_hass(hass)

        test_cases = [
            ("mp4", "extension_must_start_with_dot"),
            (".mp*", "extension_no_wildcards"),
            (".mp4/test", "extension_no_paths"),
            (".", "extension_too_short"),
        ]

        for invalid_ext, expected_error in test_cases:
            result = await hass.config_entries.options.async_init(
                mock_setup_entry.entry_id
            )

            result2 = await hass.config_entries.options.async_configure(
                result["flow_id"],
                user_input={
                    CONF_BASE_PATH: TEST_MEDIA_PATH,
                    CONF_PATTERN: "",
                    CONF_ONLY_EXTENSIONS: invalid_ext,
                    CONF_RETENTION_DAYS: TEST_RETENTION_DAYS,
                    CONF_DRY_RUN: True,
                    CONF_MAX_DELETES: TEST_MAX_DELETES,
                    CONF_RUN_AT: TEST_RUN_AT,
                },
            )

            assert (
                result2["type"] == FlowResultType.FORM
            ), f"Should reject invalid extension: {invalid_ext}"
            assert (
                expected_error in result2["errors"][CONF_ONLY_EXTENSIONS]
            ), f"Should report {expected_error} for only_extensions"
            assert (
                expected_error in result2["errors"][CONF_EXCEPT_EXTENSIONS]
            ), f"Should report {expected_error} for except_extensions"


class TestValidationFunctions:
    """Test validation functions directly for edge cases."""

    def test_validate_extensions_empty_string(self):
        """Test _validate_extensions with empty string returns empty."""
        from custom_components.retention_cleaner.config_flow import _validate_extensions

        result = _validate_extensions("")
        assert result == "", "Empty string should remain empty"

    def test_validate_pattern_empty_with_allow_empty_true(self):
        """Test _validate_pattern with empty string and allow_empty=True."""
        from custom_components.retention_cleaner.config_flow import _validate_pattern

        result = _validate_pattern("", allow_empty=True)
        assert result == "", "Empty pattern should be allowed when allow_empty=True"


class TestExtensionParsing:
    """Test extension parsing logic."""

    def test_parse_extensions_empty(self):
        """Test parsing empty extension string."""
        result = _parse_extensions("")
        assert result == set(), "Empty string should return empty set"

    def test_parse_extensions_single(self):
        """Test parsing single extension."""
        result = _parse_extensions(".mp4")
        assert result == {".mp4"}, "Single extension should be parsed correctly"

    def test_parse_extensions_multiple(self):
        """Test parsing multiple extensions."""
        result = _parse_extensions(".mp4,.jpg,.mkv")
        assert result == {
            ".mp4",
            ".jpg",
            ".mkv",
        }, "Multiple extensions should be parsed correctly"

    def test_parse_extensions_case_insensitive(self):
        """Test that extensions are converted to lowercase."""
        result = _parse_extensions(".MP4,.JPG,.MKV")
        assert result == {
            ".mp4",
            ".jpg",
            ".mkv",
        }, "Extensions should be converted to lowercase"

    def test_parse_extensions_with_spaces(self):
        """Test that spaces are trimmed."""
        result = _parse_extensions(".mp4, .jpg, .mkv")
        assert result == {
            ".mp4",
            ".jpg",
            ".mkv",
        }, "Spaces should be trimmed from extensions"

    def test_parse_extensions_with_empty_items(self):
        """Test that empty items are filtered out."""
        result = _parse_extensions(".mp4,,.jpg,,")
        assert result == {".mp4", ".jpg"}, "Empty items should be filtered out"


class TestCoordinatorOnlyExtensions:
    """Test coordinator with only_extensions filtering."""

    async def test_scan_only_extensions_filters_correctly(
        self, hass: HomeAssistant, tmp_path, create_test_files
    ):
        """Test that only_extensions filters to specified extensions."""
        media_dir = create_test_files(
            tmp_path / "media" / "only_ext_test",
            {
                "test.mp4": TEST_FILE_AGE_DAYS,
                "test.jpg": TEST_FILE_AGE_DAYS,
                "test.mkv": TEST_FILE_AGE_DAYS,
                "test.log": TEST_FILE_AGE_DAYS,
            },
        )

        result = _scan_folder(
            str(media_dir),
            "",
            TEST_RETENTION_DAYS,
            only_ext_set=_parse_extensions(".mp4,.jpg"),
        )

        assert result.total_files == 2, "Should find only .mp4 and .jpg files"
        assert result.older_than_retention == 2, "Both matching files should be old"
        assert result.path_available is True

    async def test_cleanup_only_extensions_deletes_correctly(
        self, hass: HomeAssistant, tmp_path, create_test_files
    ):
        """Test that only_extensions deletes only specified extensions."""
        media_dir = create_test_files(
            tmp_path / "media" / "cleanup_only_ext",
            {
                "test.mp4": TEST_FILE_AGE_DAYS,
                "test.jpg": TEST_FILE_AGE_DAYS,
                "test.mkv": TEST_FILE_AGE_DAYS,
                "test.log": TEST_FILE_AGE_DAYS,
            },
        )

        result = _cleanup_folder(
            str(media_dir),
            "",
            TEST_RETENTION_DAYS,
            dry_run=False,
            max_deletes=TEST_MAX_DELETES,
            only_ext_set=_parse_extensions(".mp4"),
        )

        assert result.deleted == 1, "Should delete only .mp4 file"
        assert (media_dir / "test.mkv").exists()
        assert (media_dir / "test.log").exists()
        assert (media_dir / "test.jpg").exists()
        assert not (media_dir / "test.mp4").exists()

    async def test_only_extensions_case_insensitive(
        self, hass: HomeAssistant, tmp_path, create_test_files
    ):
        """Test case-insensitive extension matching."""
        media_dir = create_test_files(
            tmp_path / "media" / "case_test",
            {
                "test.MP4": TEST_FILE_AGE_DAYS,
                "test.MKV": TEST_FILE_AGE_DAYS,
                "test.JpG": TEST_FILE_AGE_DAYS,
            },
        )

        result = _scan_folder(
            str(media_dir),
            "",
            TEST_RETENTION_DAYS,
            only_ext_set=_parse_extensions(".mp4,.jpg"),
        )

        assert result.total_files == 2, "Should match .MP4 and .JpG case-insensitively"
        assert result.older_than_retention == 2, "Both files should be old"


class TestCoordinatorExceptExtensions:
    """Test coordinator with except_extensions filtering."""

    async def test_scan_except_extensions_filters_correctly(
        self, hass: HomeAssistant, tmp_path, create_test_files
    ):
        """Test that except_extensions excludes specified extensions."""
        media_dir = create_test_files(
            tmp_path / "media" / "except_ext_test",
            {
                "test.mp4": TEST_FILE_AGE_DAYS,
                "test.mkv": TEST_FILE_AGE_DAYS,
                "test.log": TEST_FILE_AGE_DAYS,
            },
        )

        result = _scan_folder(
            str(media_dir),
            "",
            TEST_RETENTION_DAYS,
            except_ext_set=_parse_extensions(".mkv,.log"),
        )

        assert (
            result.total_files == 1
        ), "Should find only .mp4 (excluding .mkv and .log)"
        assert result.older_than_retention == 1, "The .mp4 file should be old"

    async def test_cleanup_except_extensions_preserves_correctly(
        self, hass: HomeAssistant, tmp_path, create_test_files
    ):
        """Test that except_extensions preserves excluded extensions."""
        media_dir = create_test_files(
            tmp_path / "media" / "cleanup_except",
            {
                "test.mp4": TEST_FILE_AGE_DAYS,
                "test.mkv": TEST_FILE_AGE_DAYS,
                "test.log": TEST_FILE_AGE_DAYS,
            },
        )

        result = _cleanup_folder(
            str(media_dir),
            "",
            TEST_RETENTION_DAYS,
            dry_run=False,
            max_deletes=TEST_MAX_DELETES,
            except_ext_set=_parse_extensions(".mkv,.log"),
        )

        assert result.deleted == 1, "Should delete only .mp4 file"
        assert (media_dir / "test.mkv").exists()
        assert (media_dir / "test.log").exists()
        assert not (media_dir / "test.mp4").exists()

    async def test_except_extensions_case_insensitive(
        self, hass: HomeAssistant, tmp_path, create_test_files
    ):
        """Test case-insensitive exception matching."""
        media_dir = create_test_files(
            tmp_path / "media" / "except_case_test",
            {
                "test.MKV": TEST_FILE_AGE_DAYS,
                "test.LOG": TEST_FILE_AGE_DAYS,
                "test.mp4": TEST_FILE_AGE_DAYS,
            },
        )

        result = _cleanup_folder(
            str(media_dir),
            "",
            TEST_RETENTION_DAYS,
            dry_run=False,
            max_deletes=TEST_MAX_DELETES,
            except_ext_set=_parse_extensions(".mkv,.log"),
        )

        assert result.deleted == 1, "Should delete only .mp4 file"
        assert (media_dir / "test.MKV").exists()
        assert (media_dir / "test.LOG").exists()


class TestExtensionEdgeCases:
    """Test edge cases for extension filtering."""

    async def test_extension_with_no_dot_in_filename(
        self, hass: HomeAssistant, tmp_path, create_test_files
    ):
        """Test files without extensions are handled correctly."""
        media_dir = create_test_files(
            tmp_path / "media" / "no_ext_test",
            {
                "README": TEST_FILE_AGE_DAYS,
                "test.mp4": TEST_FILE_AGE_DAYS,
            },
        )

        result = _scan_folder(
            str(media_dir),
            "",
            TEST_RETENTION_DAYS,
            only_ext_set=_parse_extensions(".mp4"),
        )

        assert result.total_files == 1, "Should find only .mp4 file, ignoring README"

    async def test_multiple_dots_in_filename(
        self, hass: HomeAssistant, tmp_path, create_test_files
    ):
        """Test files with multiple dots."""
        media_dir = create_test_files(
            tmp_path / "media" / "multi_dot_test", {"backup.tar.gz": TEST_FILE_AGE_DAYS}
        )

        result = _scan_folder(
            str(media_dir),
            "",
            TEST_RETENTION_DAYS,
            only_ext_set=_parse_extensions(".gz"),
        )

        assert result.total_files == 1, "Should match on final extension .gz"


class TestExtensionWithSafetyLimits:
    """Test extension filtering respects safety limits."""

    async def test_extension_filtering_respects_max_deletes(
        self, hass: HomeAssistant, tmp_path, create_test_files
    ):
        """Test that max_deletes limit still applies with extensions."""
        files_dict = {f"test_{i}.mp4": TEST_FILE_AGE_DAYS for i in range(20)}
        media_dir = create_test_files(
            tmp_path / "media" / "max_deletes_test", files_dict
        )

        result = _cleanup_folder(
            str(media_dir),
            "",
            TEST_RETENTION_DAYS,
            dry_run=False,
            max_deletes=10,
            only_ext_set=_parse_extensions(".mp4"),
        )

        assert result.deleted == 10, "Should respect max_deletes limit of 10"

        remaining = list(media_dir.glob("*.mp4"))
        assert len(remaining) == 10, "Should have 10 remaining files"

    async def test_extension_filtering_respects_dry_run(
        self, hass: HomeAssistant, tmp_path, create_test_files
    ):
        """Test that dry_run works with extension filtering."""
        files_dict = {f"test_{i}.mp4": TEST_FILE_AGE_DAYS for i in range(5)}
        media_dir = create_test_files(tmp_path / "media" / "dry_run_test", files_dict)

        result = _cleanup_folder(
            str(media_dir),
            "",
            TEST_RETENTION_DAYS,
            dry_run=True,
            max_deletes=TEST_MAX_DELETES,
            only_ext_set=_parse_extensions(".mp4"),
        )

        assert result.deleted == 0, "Dry run should not delete any files"

        remaining = list(media_dir.glob("*.mp4"))
        assert len(remaining) == 5, "All files should remain in dry run mode"


class TestRuntimeSafetyChecks:
    """Test runtime safety checks for empty configuration."""

    def test_scan_folder_empty_pattern_and_extensions_raises_error(
        self, tmp_path, create_test_files
    ):
        """Test that _scan_folder raises ValueError when no filters configured."""
        media_dir = create_test_files(tmp_path / "media" / "test", {})

        with pytest.raises(ValueError) as exc_info:
            _scan_folder(
                str(media_dir),
                pattern="",
                retention_days=TEST_RETENTION_DAYS,
                only_ext_set=set(),
                except_ext_set=set(),
            )

        error_msg = str(exc_info.value).lower()
        assert (
            "no filter configured" in error_msg
        ), "Should report missing filter configuration"

    def test_cleanup_folder_empty_pattern_and_extensions_raises_error(
        self, tmp_path, create_test_files
    ):
        """Test that _cleanup_folder raises ValueError when no filters configured."""
        media_dir = create_test_files(tmp_path / "media" / "test", {})

        with pytest.raises(ValueError) as exc_info:
            _cleanup_folder(
                str(media_dir),
                pattern="",
                retention_days=TEST_RETENTION_DAYS,
                dry_run=True,
                max_deletes=TEST_MAX_DELETES,
                only_ext_set=set(),
                except_ext_set=set(),
            )

        error_msg = str(exc_info.value).lower()
        assert (
            "no filter configured" in error_msg
        ), "Should report missing filter configuration"


class TestCoordinatorIntegration:
    """Test full integration with coordinator."""

    async def test_coordinator_extension_mode_full_workflow(
        self, hass: HomeAssistant, tmp_path, create_test_files
    ):
        """Test complete scan -> cleanup workflow with extensions."""
        media_dir = create_test_files(
            tmp_path / "media" / "workflow_test",
            {
                "video.mp4": TEST_FILE_AGE_DAYS,
                "photo.jpg": TEST_FILE_AGE_DAYS,
                "document.pdf": TEST_FILE_AGE_DAYS,
            },
        )

        mock_entry = MockConfigEntry(
            domain="retention_cleaner",
            title="Extension Test",
            data={
                "base_path": str(media_dir),
                "pattern": "",
                "only_extensions": ".mp4,.jpg",
                "retention_days": TEST_RETENTION_DAYS,
                "dry_run": False,
                "max_deletes": TEST_MAX_DELETES,
                "run_at": TEST_RUN_AT,
            },
            entry_id="test_ext_workflow",
        )

        coordinator = RetentionCleanerCoordinator(hass, mock_entry)

        try:
            await coordinator.async_run_scan_now()
            await hass.async_block_till_done()

            if coordinator.data is None:
                await coordinator.async_refresh()
                await hass.async_block_till_done()

            scan_result = coordinator.data
            assert scan_result is not None, "Scan should return data"
            assert scan_result["total_files"] == 2, "Should find 2 matching files"
            assert scan_result["older_than_retention"] == 2, "Both files should be old"

            await coordinator.async_run_cleanup_now()
            await hass.async_block_till_done()

            assert coordinator.deleted_last_run == 2, "Should delete 2 files"

            assert (media_dir / "document.pdf").exists()
            assert not (media_dir / "video.mp4").exists()
            assert not (media_dir / "photo.jpg").exists()

        finally:
            await coordinator.async_shutdown()
            await hass.async_block_till_done()

    async def test_pattern_mode_unchanged_with_extensions_empty(
        self, hass: HomeAssistant, tmp_path, create_test_files
    ):
        """Test that pattern mode still works when extensions empty."""
        media_dir = tmp_path / "media" / "pattern_test"
        media_dir.mkdir(parents=True)

        subdir = media_dir / "front_door"
        create_test_files(subdir, {"test.mp4": TEST_FILE_AGE_DAYS})
        create_test_files(media_dir, {"test.mp4": TEST_FILE_AGE_DAYS})

        result = _scan_folder(
            str(media_dir),
            "front_door/**/*.mp4",
            TEST_RETENTION_DAYS,
            only_ext_set=_parse_extensions(""),
        )

        assert (
            result.total_files == 1
        ), "Should find only front_door subdirectory file via pattern"

    async def test_extension_mode_searches_all_subdirs(
        self, hass: HomeAssistant, tmp_path, create_test_files
    ):
        """Test that extension mode searches all subdirectories."""
        media_dir = tmp_path / "media" / "deep_test"
        deep_dir = media_dir / "a" / "b" / "c"

        create_test_files(deep_dir, {"test.mp4": TEST_FILE_AGE_DAYS})

        result = _scan_folder(
            str(media_dir),
            "",
            TEST_RETENTION_DAYS,
            only_ext_set=_parse_extensions(".mp4"),
        )

        assert result.total_files == 1, "Should find file in deeply nested subdirectory"
