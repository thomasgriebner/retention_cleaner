"""Test max_files_in_folder feature."""

import os

from homeassistant.core import HomeAssistant
import pytest

from custom_components.retention_cleaner.coordinator import RetentionCleanerCoordinator
from tests.conftest import (
    TEST_FILE_AGE_NEW,
    TEST_FILE_AGE_OLD,
    TEST_FILE_COUNT_MEDIUM,
    TEST_MAX_DELETES,
    TEST_RETENTION_DAYS,
)


async def test_max_files_enforced_after_time_based_cleanup(
    hass: HomeAssistant, tmp_path, create_numbered_files, mock_max_files_config
):
    """Test that max_files_in_folder is enforced after time-based cleanup."""
    media_dir = tmp_path / "media" / "test"
    max_files_limit = 10

    create_numbered_files(
        media_dir, count=TEST_FILE_COUNT_MEDIUM, age_days=TEST_FILE_AGE_NEW
    )
    mock_entry = mock_max_files_config(
        base_path=str(media_dir),
        max_files=max_files_limit,
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        if coordinator.data is None:
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"

        files_to_delete = TEST_FILE_COUNT_MEDIUM - max_files_limit
        assert (
            result["deleted_last_run"] == files_to_delete
        ), f"Should delete {files_to_delete} oldest files to reach max_files_in_folder={max_files_limit}"
        assert (
            result["total_files"] == max_files_limit
        ), f"Should have {max_files_limit} files remaining"

        for i in range(files_to_delete):
            file = media_dir / f"file_{i:02d}.jpg"
            assert not file.exists(), f"Oldest file file_{i:02d}.jpg should be deleted"

        for i in range(files_to_delete, TEST_FILE_COUNT_MEDIUM):
            file = media_dir / f"file_{i:02d}.jpg"
            assert file.exists(), f"Newest file file_{i:02d}.jpg should be kept"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_zero_disables_feature(
    hass: HomeAssistant, tmp_path, create_numbered_files, mock_max_files_config
):
    """Test that max_files_in_folder=0 disables the feature."""
    media_dir = tmp_path / "media" / "test"
    file_count = 50

    create_numbered_files(media_dir, count=file_count, age_days=TEST_FILE_AGE_NEW)
    mock_entry = mock_max_files_config(
        base_path=str(media_dir),
        max_files=0,
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        if coordinator.data is None:
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"

        assert (
            result["deleted_last_run"] == 0
        ), "Should not delete any files when max_files_in_folder=0 (disabled)"
        assert (
            result["total_files"] == file_count
        ), f"Should keep all {file_count} files when feature disabled"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_respects_max_deletes(
    hass: HomeAssistant, tmp_path, create_numbered_files, mock_max_files_config
):
    """Test that max_files_in_folder respects max_deletes limit."""
    media_dir = tmp_path / "media" / "test"
    max_deletes_limit = 5
    max_files_limit = 10

    create_numbered_files(
        media_dir, count=TEST_FILE_COUNT_MEDIUM, age_days=TEST_FILE_AGE_NEW
    )
    mock_entry = mock_max_files_config(
        base_path=str(media_dir),
        max_deletes=max_deletes_limit,
        max_files=max_files_limit,
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        if coordinator.data is None:
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"

        assert (
            result["deleted_last_run"] == max_deletes_limit
        ), f"Should respect max_deletes limit of {max_deletes_limit}"
        expected_remaining = TEST_FILE_COUNT_MEDIUM - max_deletes_limit
        assert (
            result["total_files"] == expected_remaining
        ), f"Should have {expected_remaining} files remaining after max_deletes limit"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_with_time_based_deletion_combined(
    hass: HomeAssistant, tmp_path, create_numbered_files, mock_max_files_config
):
    """Test max_files_in_folder works with time-based deletion."""
    media_dir = tmp_path / "media" / "test"
    old_files_count = 10
    new_files_count = 20
    total_files = old_files_count + new_files_count
    max_files_limit = 15

    create_numbered_files(
        media_dir, count=old_files_count, age_days=TEST_FILE_AGE_OLD, ext=".jpg"
    )

    for i in range(old_files_count, total_files):
        import time as time_module

        file = media_dir / f"file_{i:02d}.jpg"
        file.write_text(f"content {i}")
        new_time = time_module.time() - (TEST_FILE_AGE_NEW * 24 * 60 * 60)
        os.utime(file, (new_time, new_time))

    mock_entry = mock_max_files_config(
        base_path=str(media_dir),
        max_files=max_files_limit,
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        if coordinator.data is None:
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"

        time_based_deletions = old_files_count
        files_after_time_cleanup = total_files - time_based_deletions
        count_based_deletions = files_after_time_cleanup - max_files_limit
        total_deletions = time_based_deletions + count_based_deletions

        assert (
            result["deleted_last_run"] == total_deletions
        ), f"Should delete {time_based_deletions} old + {count_based_deletions} for count limit"
        assert (
            result["total_files"] == max_files_limit
        ), f"Should have {max_files_limit} files remaining (max_files_in_folder)"

        for i in range(old_files_count):
            file = media_dir / f"file_{i:02d}.jpg"
            assert (
                not file.exists()
            ), f"Old file file_{i:02d}.jpg should be deleted by time-based cleanup"

        for i in range(old_files_count, old_files_count + count_based_deletions):
            file = media_dir / f"file_{i:02d}.jpg"
            assert (
                not file.exists()
            ), f"File file_{i:02d}.jpg should be deleted to reach count limit"

        for i in range(old_files_count + count_based_deletions, total_files):
            file = media_dir / f"file_{i:02d}.jpg"
            assert file.exists(), f"File file_{i:02d}.jpg should be kept (newest files)"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_dry_run_mode(
    hass: HomeAssistant, tmp_path, create_numbered_files, mock_max_files_config
):
    """Test that dry run mode shows what would be deleted by max_files_in_folder."""
    media_dir = tmp_path / "media" / "test"
    max_files_limit = 10

    create_numbered_files(
        media_dir, count=TEST_FILE_COUNT_MEDIUM, age_days=TEST_FILE_AGE_NEW
    )
    mock_entry = mock_max_files_config(
        base_path=str(media_dir),
        dry_run=True,
        max_files=max_files_limit,
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        if coordinator.data is None:
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"

        assert (
            result["deleted_last_run"] == 0
        ), "Dry run should not actually delete files"
        assert (
            result["total_files"] == TEST_FILE_COUNT_MEDIUM
        ), f"All {TEST_FILE_COUNT_MEDIUM} files should still exist in dry run"

        for i in range(TEST_FILE_COUNT_MEDIUM):
            file = media_dir / f"file_{i:02d}.jpg"
            assert (
                file.exists()
            ), f"File file_{i:02d}.jpg should still exist in dry run mode"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_takes_priority_over_keep_minimum(
    hass: HomeAssistant, tmp_path, create_numbered_files, mock_max_files_config
):
    """Test that max_files_in_folder takes priority over keep_minimum_files."""
    media_dir = tmp_path / "media" / "test"
    file_count = 30
    keep_minimum = 20
    max_files_limit = 10

    create_numbered_files(media_dir, count=file_count, age_days=TEST_FILE_AGE_NEW)
    mock_entry = mock_max_files_config(
        base_path=str(media_dir),
        keep_minimum=keep_minimum,
        max_files=max_files_limit,
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        if coordinator.data is None:
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"

        expected_deletions = file_count - max_files_limit
        assert (
            result["deleted_last_run"] == expected_deletions
        ), f"Should delete {expected_deletions} files despite keep_minimum={keep_minimum}"
        assert (
            result["total_files"] == max_files_limit
        ), f"Should have {max_files_limit} files (max_files_in_folder takes priority over keep_minimum_files)"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_counts_protected_files(
    hass: HomeAssistant, tmp_path, create_numbered_files, mock_max_files_config
):
    """Test that protected files count toward max_files_in_folder limit."""
    media_dir = tmp_path / "media" / "test"
    file_count = 20
    keep_minimum = 15
    max_files_limit = 10
    short_retention = 2

    create_numbered_files(media_dir, count=file_count, age_days=5)
    mock_entry = mock_max_files_config(
        base_path=str(media_dir),
        retention_days=short_retention,
        keep_minimum=keep_minimum,
        max_files=max_files_limit,
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        if coordinator.data is None:
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"

        assert (
            result["total_files"] == max_files_limit
        ), f"Should have {max_files_limit} files (max_files_in_folder takes priority over keep_minimum_files)"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("file_count", "max_files", "expected_deleted"),
    [
        (5, 10, 0),
        (10, 10, 0),
        (15, 10, 5),
        (100, 50, 50),
    ],
)
async def test_max_files_various_scenarios(
    hass: HomeAssistant,
    tmp_path,
    create_numbered_files,
    mock_max_files_config,
    file_count,
    max_files,
    expected_deleted,
):
    """Test max_files_in_folder with various file counts and limits."""
    media_dir = tmp_path / "media" / "test"

    create_numbered_files(media_dir, count=file_count, age_days=TEST_FILE_AGE_NEW)
    mock_entry = mock_max_files_config(
        base_path=str(media_dir),
        max_files=max_files,
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        if coordinator.data is None:
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"

        assert (
            result["deleted_last_run"] == expected_deleted
        ), f"Should delete {expected_deleted} files when file_count={file_count}, max_files={max_files}"
        expected_remaining = min(file_count, max_files)
        assert (
            result["total_files"] == expected_remaining
        ), f"Should have {expected_remaining} files remaining"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_with_max_deletes_and_old_files(
    hass: HomeAssistant, tmp_path, create_numbered_files, mock_max_files_config
):
    """Test max_files_in_folder when max_deletes prevents time-based deletion."""
    media_dir = tmp_path / "media" / "test"
    old_files_count = 20
    new_files_count = 10
    total_files = old_files_count + new_files_count
    max_deletes_limit = 5
    max_files_limit = 15

    create_numbered_files(
        media_dir, count=old_files_count, age_days=TEST_FILE_AGE_OLD, ext=".jpg"
    )

    for i in range(old_files_count, total_files):
        import time as time_module

        file = media_dir / f"file_{i:02d}.jpg"
        file.write_text(f"content {i}")
        new_time = time_module.time() - (TEST_FILE_AGE_NEW * 24 * 60 * 60)
        os.utime(file, (new_time, new_time))

    mock_entry = mock_max_files_config(
        base_path=str(media_dir),
        max_deletes=max_deletes_limit,
        max_files=max_files_limit,
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        if coordinator.data is None:
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"

        assert (
            result["deleted_last_run"] == max_deletes_limit
        ), f"Should only delete {max_deletes_limit} files (max_deletes limit)"
        expected_remaining = total_files - max_deletes_limit
        assert (
            result["total_files"] == expected_remaining
        ), f"Should have {expected_remaining} files (max_deletes prevents reaching max_files_in_folder limit)"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_with_only_extensions(
    hass: HomeAssistant, tmp_path, create_test_files, mock_max_files_config
):
    """Test max_files_in_folder counts and deletes only specified extensions."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.retention_cleaner.coordinator import (
        RetentionCleanerCoordinator,
    )

    media_dir = tmp_path / "media" / "only_ext_test"
    media_dir.mkdir(parents=True)

    import os
    import time as time_module

    mp4_file_count = 120
    jpg_file_count = 50
    max_files_limit = 100

    for i in range(mp4_file_count):
        file = media_dir / f"video_{i:03d}.mp4"
        file.write_text(f"video content {i}")
        file_time = time_module.time() - (TEST_FILE_AGE_NEW * 24 * 60 * 60)
        os.utime(file, (file_time, file_time))

    for i in range(jpg_file_count):
        file = media_dir / f"photo_{i:03d}.jpg"
        file.write_text(f"photo content {i}")
        file_time = time_module.time() - (TEST_FILE_AGE_NEW * 24 * 60 * 60)
        os.utime(file, (file_time, file_time))

    mock_entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Max Files with Only Extensions",
        data={
            "base_path": str(media_dir),
            "pattern": "",
            "only_extensions": ".mp4",
            "retention_days": TEST_RETENTION_DAYS,
            "dry_run": False,
            "max_deletes": TEST_MAX_DELETES,
            "max_files_in_folder": max_files_limit,
        },
        entry_id="test_max_files_only_ext",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        if coordinator.data is None:
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"

        mp4_files_remaining = list(media_dir.glob("*.mp4"))
        jpg_files_remaining = list(media_dir.glob("*.jpg"))

        expected_mp4_deleted = mp4_file_count - max_files_limit
        assert (
            result["deleted_last_run"] == expected_mp4_deleted
        ), f"Should delete {expected_mp4_deleted} oldest .mp4 files to reach limit"

        assert (
            len(mp4_files_remaining) == max_files_limit
        ), f"Should have exactly {max_files_limit} .mp4 files remaining"

        assert (
            len(jpg_files_remaining) == jpg_file_count
        ), f"All {jpg_file_count} .jpg files should remain untouched"

        for i in range(expected_mp4_deleted):
            file = media_dir / f"video_{i:03d}.mp4"
            assert (
                not file.exists()
            ), f"Oldest .mp4 file video_{i:03d}.mp4 should be deleted"

        for i in range(expected_mp4_deleted, mp4_file_count):
            file = media_dir / f"video_{i:03d}.mp4"
            assert file.exists(), f"Newer .mp4 file video_{i:03d}.mp4 should be kept"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_with_except_extensions(
    hass: HomeAssistant, tmp_path, create_test_files, mock_max_files_config
):
    """Test max_files_in_folder excludes except_extensions from counting and deletion."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.retention_cleaner.coordinator import (
        RetentionCleanerCoordinator,
    )

    media_dir = tmp_path / "media" / "except_ext_test"
    media_dir.mkdir(parents=True)

    import os
    import time as time_module

    mp4_file_count = 120
    log_file_count = 50
    max_files_limit = 100

    for i in range(mp4_file_count):
        file = media_dir / f"video_{i:03d}.mp4"
        file.write_text(f"video content {i}")
        file_time = time_module.time() - (TEST_FILE_AGE_NEW * 24 * 60 * 60)
        os.utime(file, (file_time, file_time))

    for i in range(log_file_count):
        file = media_dir / f"system_{i:03d}.log"
        file.write_text(f"log content {i}")
        file_time = time_module.time() - (TEST_FILE_AGE_NEW * 24 * 60 * 60)
        os.utime(file, (file_time, file_time))

    mock_entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Max Files with Except Extensions",
        data={
            "base_path": str(media_dir),
            "pattern": "",
            "except_extensions": ".log",
            "retention_days": TEST_RETENTION_DAYS,
            "dry_run": False,
            "max_deletes": TEST_MAX_DELETES,
            "max_files_in_folder": max_files_limit,
        },
        entry_id="test_max_files_except_ext",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        if coordinator.data is None:
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"

        mp4_files_remaining = list(media_dir.glob("*.mp4"))
        log_files_remaining = list(media_dir.glob("*.log"))

        expected_mp4_deleted = mp4_file_count - max_files_limit
        assert (
            result["deleted_last_run"] == expected_mp4_deleted
        ), f"Should delete {expected_mp4_deleted} oldest .mp4 files to reach limit"

        assert (
            len(mp4_files_remaining) == max_files_limit
        ), f"Should have exactly {max_files_limit} .mp4 files remaining"

        assert (
            len(log_files_remaining) == log_file_count
        ), f"All {log_file_count} .log files should be protected and remain"

        for i in range(expected_mp4_deleted):
            file = media_dir / f"video_{i:03d}.mp4"
            assert (
                not file.exists()
            ), f"Oldest .mp4 file video_{i:03d}.mp4 should be deleted"

        for i in range(expected_mp4_deleted, mp4_file_count):
            file = media_dir / f"video_{i:03d}.mp4"
            assert file.exists(), f"Newer .mp4 file video_{i:03d}.mp4 should be kept"

        for i in range(log_file_count):
            file = media_dir / f"system_{i:03d}.log"
            assert (
                file.exists()
            ), f"Protected .log file system_{i:03d}.log should remain"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_with_only_extensions_and_keep_minimum(
    hass: HomeAssistant, tmp_path, create_test_files, mock_max_files_config
):
    """Test max_files_in_folder takes priority over keep_minimum_files with extension filtering."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.retention_cleaner.coordinator import (
        RetentionCleanerCoordinator,
    )

    media_dir = tmp_path / "media" / "complex_test"
    media_dir.mkdir(parents=True)

    import os
    import time as time_module

    mp4_file_count = 30
    jpg_file_count = 20
    keep_minimum = 25
    max_files_limit = 10

    for i in range(mp4_file_count):
        file = media_dir / f"video_{i:03d}.mp4"
        file.write_text(f"video content {i}")
        file_time = time_module.time() - (TEST_FILE_AGE_NEW * 24 * 60 * 60)
        os.utime(file, (file_time, file_time))

    for i in range(jpg_file_count):
        file = media_dir / f"photo_{i:03d}.jpg"
        file.write_text(f"photo content {i}")
        file_time = time_module.time() - (TEST_FILE_AGE_NEW * 24 * 60 * 60)
        os.utime(file, (file_time, file_time))

    mock_entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Max Files Priority",
        data={
            "base_path": str(media_dir),
            "pattern": "",
            "only_extensions": ".mp4",
            "retention_days": TEST_RETENTION_DAYS,
            "dry_run": False,
            "max_deletes": TEST_MAX_DELETES,
            "keep_minimum_files": keep_minimum,
            "max_files_in_folder": max_files_limit,
        },
        entry_id="test_max_files_priority",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        if coordinator.data is None:
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"

        mp4_files_remaining = list(media_dir.glob("*.mp4"))
        jpg_files_remaining = list(media_dir.glob("*.jpg"))

        expected_mp4_deleted = mp4_file_count - max_files_limit
        assert (
            result["deleted_last_run"] == expected_mp4_deleted
        ), f"Should delete {expected_mp4_deleted} .mp4 files (max_files_in_folder takes priority over keep_minimum_files)"

        assert (
            len(mp4_files_remaining) == max_files_limit
        ), f"Should have exactly {max_files_limit} .mp4 files (not {keep_minimum})"

        assert (
            len(jpg_files_remaining) == jpg_file_count
        ), f"All {jpg_file_count} .jpg files should remain untouched"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()


async def test_max_files_with_except_extensions_and_max_deletes(
    hass: HomeAssistant, tmp_path, create_test_files, mock_max_files_config
):
    """Test max_deletes stops deletion even with max_files_in_folder and except_extensions."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.retention_cleaner.coordinator import (
        RetentionCleanerCoordinator,
    )

    media_dir = tmp_path / "media" / "max_deletes_test"
    media_dir.mkdir(parents=True)

    import os
    import time as time_module

    mp4_file_count = 50
    log_file_count = 10
    max_files_limit = 20
    max_deletes_limit = 10

    for i in range(mp4_file_count):
        file = media_dir / f"video_{i:03d}.mp4"
        file.write_text(f"video content {i}")
        file_time = time_module.time() - (TEST_FILE_AGE_NEW * 24 * 60 * 60)
        os.utime(file, (file_time, file_time))

    for i in range(log_file_count):
        file = media_dir / f"system_{i:03d}.log"
        file.write_text(f"log content {i}")
        file_time = time_module.time() - (TEST_FILE_AGE_NEW * 24 * 60 * 60)
        os.utime(file, (file_time, file_time))

    mock_entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Max Deletes with Except",
        data={
            "base_path": str(media_dir),
            "pattern": "",
            "except_extensions": ".log",
            "retention_days": TEST_RETENTION_DAYS,
            "dry_run": False,
            "max_deletes": max_deletes_limit,
            "max_files_in_folder": max_files_limit,
        },
        entry_id="test_max_deletes_except",
    )

    coordinator = RetentionCleanerCoordinator(hass, mock_entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        if coordinator.data is None:
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        result = coordinator.data
        assert result is not None, "Coordinator data should not be None"

        mp4_files_remaining = list(media_dir.glob("*.mp4"))
        log_files_remaining = list(media_dir.glob("*.log"))

        assert (
            result["deleted_last_run"] == max_deletes_limit
        ), f"Should stop at max_deletes={max_deletes_limit} even though file count exceeds max_files_in_folder"

        expected_mp4_remaining = mp4_file_count - max_deletes_limit
        assert (
            len(mp4_files_remaining) == expected_mp4_remaining
        ), f"Should have {expected_mp4_remaining} .mp4 files (stopped by max_deletes)"

        assert (
            len(log_files_remaining) == log_file_count
        ), f"All {log_file_count} .log files should be protected"

        for i in range(max_deletes_limit):
            file = media_dir / f"video_{i:03d}.mp4"
            assert (
                not file.exists()
            ), f"Oldest .mp4 file video_{i:03d}.mp4 should be deleted"

        for i in range(max_deletes_limit, mp4_file_count):
            file = media_dir / f"video_{i:03d}.mp4"
            assert file.exists(), f"Newer .mp4 file video_{i:03d}.mp4 should remain (max_deletes limit reached)"

    finally:
        await coordinator.async_shutdown()
        await hass.async_block_till_done()
