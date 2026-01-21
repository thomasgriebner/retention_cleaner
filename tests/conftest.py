"""Test configuration and fixtures for retention_cleaner tests."""

from pathlib import Path
import sys

# Ensure custom_components is importable (needed for direct function imports in sync tests)
_repo_root = Path(__file__).parent.parent.absolute()
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import contextlib
from unittest.mock import Mock, patch

from freezegun import freeze_time
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest

# Enable pytest-homeassistant-custom-component fixtures
pytest_plugins = "pytest_homeassistant_custom_component"


# Test Constants
TEST_MEDIA_PATH = "/media/test"
TEST_RETENTION_DAYS = 7
TEST_FILE_AGE_DAYS = 8  # Files older than retention
TEST_MAX_DELETES = 100
TEST_DRY_RUN = True
TEST_RUN_AT = "02:00"
TEST_KEEP_MINIMUM_FILES = 5
TEST_MAX_FILES_IN_FOLDER = 50
TEST_REMOVE_EMPTY_FOLDERS = False  # Default for opt-in feature

# Test file count constants
TEST_FILE_COUNT_SMALL = 5
TEST_FILE_COUNT_MEDIUM = 20
TEST_FILE_COUNT_LARGE = 50
TEST_FILE_AGE_NEW = 2  # Days (within retention)
TEST_FILE_AGE_OLD = TEST_FILE_AGE_DAYS  # Use the existing constant

# Hidden file names for empty directory tests
TEST_HIDDEN_FILE_GITKEEP = ".gitkeep"
TEST_HIDDEN_FILE_DS_STORE = ".DS_Store"
TEST_HIDDEN_FILE_KEEP = ".keep"

# Directory depth constants for nested tests
TEST_DIR_DEPTH_SHALLOW = 1
TEST_DIR_DEPTH_MEDIUM = 3
TEST_DIR_DEPTH_DEEP = 5

# File size constants (bytes) for size sensor tests
TEST_FILE_SIZE_SMALL = 1024  # 1 KB
TEST_FILE_SIZE_MEDIUM = 102400  # 100 KB
TEST_FILE_SIZE_LARGE = 1048576  # 1 MB


def pytest_configure(config):
    """Configure pytest - ensures custom_components is in sys.path early."""
    repo_root = Path(__file__).parent.parent.absolute()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


# Test Helper Functions
async def assert_exception_chain(operation, expected_error_type, expected_message):
    """Helper to verify complete exception chain.

    Args:
        operation: Async callable that should raise exception
        expected_error_type: Expected exception class
        expected_message: Message that should be in exception

    Returns:
        The exception info for further assertions
    """
    with pytest.raises(expected_error_type) as exc_info:
        await operation()

    assert expected_message in str(exc_info.value)
    return exc_info


async def verify_cleanup_exception_handling(coordinator, exception_to_raise):
    """Verify cleanup operation handles exception correctly.

    Tests the complete chain:
    filesystem error -> RuntimeError -> UpdateFailed
    """
    # Mock Path where it's actually used in the coordinator module
    with patch(
        "custom_components.retention_cleaner.coordinator.Path",
    ) as mock_path_class:
        # Create a mock Path instance that raises the exception on glob
        mock_path_instance = Mock()
        mock_path_class.return_value = mock_path_instance
        mock_path_instance.glob.side_effect = exception_to_raise
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_dir.return_value = True

        return await assert_exception_chain(
            coordinator.async_run_cleanup_now, UpdateFailed, "Cleanup failed:"
        )


async def verify_scan_exception_handling(coordinator, exception_to_raise):
    """Verify scan operation handles exception correctly.

    Tests the complete chain:
    filesystem error -> RuntimeError -> UpdateFailed
    """
    # Mock Path where it's actually used in the coordinator module
    with patch(
        "custom_components.retention_cleaner.coordinator.Path",
    ) as mock_path_class:
        # Create a mock Path instance that raises the exception on glob
        mock_path_instance = Mock()
        mock_path_class.return_value = mock_path_instance
        mock_path_instance.glob.side_effect = exception_to_raise
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_dir.return_value = True

        return await assert_exception_chain(
            coordinator.async_run_scan_now, UpdateFailed, "Scan failed:"
        )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integration for all tests."""
    yield


@pytest.fixture
def mock_setup_entry():
    """Create a mock config entry for testing."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    return MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
            "dry_run": True,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_entry_123",
    )


@pytest.fixture
def mock_setup_entry_no_dry_run():
    """Create a mock config entry with dry run disabled."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    return MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup No Dry Run",
        data={
            "base_path": "/media/test",
            "pattern": "*.log",
            "retention_days": 3,
            "dry_run": False,
            "max_deletes": 50,
            "run_at": "04:00",
        },
        entry_id="test_entry_456",
    )


async def _setup_integration_base(
    hass, entry, mock_glob=True, glob_return_value=None, keep_mocks=False
):
    """Shared integration setup logic.

    Args:
        hass: Home Assistant instance
        entry: Config entry to setup
        mock_glob: Whether to mock Path.glob
        glob_return_value: Value to return from Path.glob mock
        keep_mocks: If True, return active mock context manager
    """
    entry.add_to_hass(hass)

    # Build patch list based on parameters
    patches = [
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
    ]

    if mock_glob:
        if glob_return_value is not None:
            patches.append(patch("pathlib.Path.glob", return_value=glob_return_value))
        else:
            patches.append(patch("pathlib.Path.glob", return_value=[]))

    if keep_mocks:
        # Keep mocks active and return them with the entry
        stack = contextlib.ExitStack()
        mock_objects = {}
        for p in patches:
            mock_obj = stack.enter_context(p)
            # Store references to the mock objects
            if "exists" in str(p):
                mock_objects["exists"] = mock_obj
            elif "is_dir" in str(p):
                mock_objects["is_dir"] = mock_obj
            elif "glob" in str(p):
                mock_objects["glob"] = mock_obj

        # Setup the integration with mocks active
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Store mocks and stack on entry for cleanup
        entry._mock_stack = stack
        entry._mock_objects = mock_objects
    else:
        # Original behavior - mocks only during setup
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            # Setup the integration
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

    # Verify runtime_data was set during setup
    assert hasattr(entry, "runtime_data")
    assert entry.runtime_data is not None

    return entry


@pytest.fixture
async def init_integration(hass, mock_setup_entry):
    """Set up the retention_cleaner integration with default mocks."""
    return await _setup_integration_base(hass, mock_setup_entry, mock_glob=True)


@pytest.fixture
async def init_integration_with_exception(hass, mock_setup_entry, request):
    """Set up integration with configurable exception on Path.glob.

    Usage in test:
        @pytest.mark.parametrize(
            "init_integration_with_exception",
            [{"exception": PermissionError("No access")}],
            indirect=True
        )
        async def test_permission_error(init_integration_with_exception):
            ...
    """
    exception = request.param.get("exception", Exception("Test error"))

    entry = await _setup_integration_base(hass, mock_setup_entry, mock_glob=False)

    # Patch Path.glob at coordinator module level to raise exception
    with patch(
        "custom_components.retention_cleaner.coordinator.Path.glob",
        side_effect=exception,
    ):
        yield entry


@pytest.fixture
def mock_coordinator_data():
    """Mock coordinator data for entity tests."""
    from datetime import UTC, datetime

    return {
        "total_files": 100,
        "older_than_retention": 25,
        "deleted_last_run": 10,
        "deleted_bytes_last_run": 102400,
        "last_scan": datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        "last_cleanup": datetime(2024, 1, 1, 2, 0, 0, tzinfo=UTC),
        "last_scan_duration_ms": 150,  # int milliseconds
        "last_cleanup_duration_ms": 500,  # int milliseconds
        "path_available": True,
        "total_folder_size_bytes": 2097152,  # 2 MB
        "older_than_retention_size_bytes": 1048576,  # 1 MB
    }


@pytest.fixture
def freezer():
    """Freeze time for testing scheduled operations."""
    with freeze_time("2024-01-01 12:00:00") as frozen_time:
        yield frozen_time


@pytest.fixture
def create_test_files():
    """Factory fixture to create test files with specified ages.

    Usage:
        files = create_test_files(tmp_path / "media", {
            "test.mp4": 8,  # 8 days old
            "test.jpg": 5,  # 5 days old
        })

    Returns:
        Callable that creates files and returns the directory path.
    """

    def _create_files(base_dir: Path, files: dict[str, int]) -> Path:
        """Create test files with specified ages.

        Args:
            base_dir: Directory to create files in
            files: Dict mapping filename -> age_in_days

        Returns:
            Path: The base directory
        """
        import os
        import time as time_module

        base_dir.mkdir(parents=True, exist_ok=True)

        for filename, age_days in files.items():
            file_path = base_dir / filename
            file_path.write_text(f"content of {filename}")

            old_time = time_module.time() - (age_days * 24 * 60 * 60)
            os.utime(file_path, (old_time, old_time))

        return base_dir

    return _create_files


@pytest.fixture
def create_numbered_files():
    """Factory fixture to create numbered test files with specified ages.

    Usage:
        base_dir = create_numbered_files(tmp_path / "media", count=20, age_days=2, ext=".jpg")

    Returns:
        Callable that creates numbered files and returns the directory path.
    """

    def _create_files(
        base_dir: Path, count: int, age_days: int, ext: str = ".jpg"
    ) -> Path:
        """Create numbered test files with specified age.

        Args:
            base_dir: Directory to create files in
            count: Number of files to create
            age_days: Age in days for all files
            ext: File extension (default .jpg)

        Returns:
            Path: The base directory
        """
        import os
        import time as time_module

        base_dir.mkdir(parents=True, exist_ok=True)

        for i in range(count):
            file_path = base_dir / f"file_{i:02d}{ext}"
            file_path.write_text(f"content {i}")

            file_time = time_module.time() - (age_days * 24 * 60 * 60)
            os.utime(file_path, (file_time, file_time))

        return base_dir

    return _create_files


@pytest.fixture
def mock_extension_config():
    """Create a mock config entry for extension mode testing."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    return MockConfigEntry(
        domain="retention_cleaner",
        title="Test Extension Mode",
        data={
            "base_path": TEST_MEDIA_PATH,
            "pattern": "",  # Empty in extension mode
            "only_extensions": ".mp4,.jpg",
            "except_extensions": "",
            "retention_days": TEST_RETENTION_DAYS,
            "dry_run": TEST_DRY_RUN,
            "max_deletes": TEST_MAX_DELETES,
            "run_at": TEST_RUN_AT,
        },
        entry_id="test_ext_entry_789",
    )


@pytest.fixture
def mock_max_files_config():
    """Factory fixture to create mock config entry with customizable max_files_in_folder.

    Usage:
        entry = mock_max_files_config(base_path=str(tmp_path), max_files=10, dry_run=False)
    """
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    def _create_config(
        base_path=TEST_MEDIA_PATH,
        pattern="*.jpg",
        retention_days=TEST_RETENTION_DAYS,
        dry_run=False,
        max_deletes=TEST_MAX_DELETES,
        max_files=0,
        keep_minimum=0,
    ):
        return MockConfigEntry(
            domain="retention_cleaner",
            title="Test Max Files",
            data={
                "base_path": base_path,
                "pattern": pattern,
                "retention_days": retention_days,
                "dry_run": dry_run,
                "max_deletes": max_deletes,
                "max_files_in_folder": max_files,
                "keep_minimum_files": keep_minimum,
            },
            entry_id="test_max_files_entry",
        )

    return _create_config


@pytest.fixture
async def extension_config_flow(hass):
    """Helper fixture for testing extension filtering config flows.

    Simplifies the repetitive pattern of:
    - async_init flow
    - async_configure with user input
    - optional mock of async_setup_entry

    Usage:
        result = await extension_config_flow({"only_extensions": ".mp4"})
        result = await extension_config_flow({"only_extensions": ".mp4"}, expect_success=True)
    """
    from homeassistant import config_entries

    async def _flow(user_input: dict, expect_success: bool = False):
        """Run config flow with given user input.

        Args:
            user_input: Dict with config values (CONF_BASE_PATH, etc.)
            expect_success: If True, mock async_setup_entry for success path

        Returns:
            FlowResult from async_configure
        """
        result = await hass.config_entries.flow.async_init(
            "retention_cleaner", context={"source": config_entries.SOURCE_USER}
        )

        if expect_success:
            with patch(
                "custom_components.retention_cleaner.async_setup_entry",
                return_value=True,
            ):
                return await hass.config_entries.flow.async_configure(
                    result["flow_id"], user_input
                )
        else:
            return await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )

    return _flow


@pytest.fixture
def create_nested_dirs():
    """Factory fixture to create nested directory structures for testing.

    Usage:
        base, dirs = create_nested_dirs(tmp_path / "media", depth=3, files_in_leaf=False)

    Returns:
        Callable that creates nested directories and returns (base_path, [all_dir_paths]).
    """

    def _create(
        base_dir: Path, depth: int, files_in_leaf: bool = False
    ) -> tuple[Path, list[Path]]:
        """Create nested directory structure.

        Args:
            base_dir: Root directory to create structure in
            depth: Number of nested levels (1 = base/level1, 2 = base/level1/level2, etc.)
            files_in_leaf: If True, add a test file in the deepest directory

        Returns:
            Tuple of (base_dir, list of all created directory paths)
        """
        base_dir.mkdir(parents=True, exist_ok=True)
        created_dirs = []

        current = base_dir
        for i in range(1, depth + 1):
            current = current / f"level{i}"
            current.mkdir(exist_ok=True)
            created_dirs.append(current)

        if files_in_leaf and created_dirs:
            test_file = created_dirs[-1] / "test.jpg"
            test_file.write_text("test content")

        return base_dir, created_dirs

    return _create


@pytest.fixture
def mock_remove_empty_config():
    """Factory fixture to create mock config entry with remove_empty_folders option.

    Usage:
        entry = mock_remove_empty_config(
            base_path=str(tmp_path),
            remove_empty=True,
            dry_run=False
        )
    """
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    def _create_config(
        base_path=TEST_MEDIA_PATH,
        pattern="**/*.jpg",
        retention_days=TEST_RETENTION_DAYS,
        dry_run=False,
        max_deletes=TEST_MAX_DELETES,
        remove_empty=False,
    ):
        return MockConfigEntry(
            domain="retention_cleaner",
            title="Test Remove Empty Folders",
            data={
                "base_path": base_path,
                "pattern": pattern,
                "retention_days": retention_days,
                "dry_run": dry_run,
                "max_deletes": max_deletes,
                "remove_empty_folders": remove_empty,
            },
            entry_id="test_remove_empty_entry",
        )

    return _create_config
