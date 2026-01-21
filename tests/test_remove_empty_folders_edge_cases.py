"""Additional edge case tests for remove empty folders feature to reach 100% coverage."""

import errno
import os
from pathlib import Path
import time as time_module
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.retention_cleaner.coordinator import RetentionCleanerCoordinator
from tests.conftest import (
    TEST_FILE_AGE_DAYS,
)


async def test_directory_already_processed_in_round(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path
):
    """Test that directories already processed in a round are skipped (line 368)."""
    from custom_components.retention_cleaner.coordinator import (
        _remove_empty_directories,
    )

    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)

    subdir = media_dir / "subfolder"
    subdir.mkdir()
    file1 = subdir / "old1.jpg"
    file1.write_text("old content 1")

    old_time = time_module.time() - (TEST_FILE_AGE_DAYS * 24 * 60 * 60)
    os.utime(file1, (old_time, old_time))

    file1.unlink()

    deleted_paths = {file1}

    original_sorted = sorted

    def track_sorted(iterable, *args, **kwargs):
        result_list = original_sorted(iterable, *args, **kwargs)
        if result_list and isinstance(result_list[0], Path):
            if len(result_list) > 0:
                result_list.append(result_list[0])
        return result_list

    with (
        patch("custom_components.retention_cleaner.coordinator.sorted", track_sorted),
    ):
        removed_count = _remove_empty_directories(
            base_path=str(media_dir), deleted_file_paths=deleted_paths, dry_run=False
        )

    assert removed_count >= 1, "Should remove at least subfolder"
    assert not subdir.exists(), "Subfolder should be removed"


async def test_directory_not_exists_during_check(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path
):
    """Test handling when directory doesn't exist during check (line 373)."""
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)

    subdir = media_dir / "subfolder"
    subdir.mkdir()
    old_file = subdir / "old.jpg"
    old_file.write_text("old content")

    old_time = time_module.time() - (TEST_FILE_AGE_DAYS * 24 * 60 * 60)
    os.utime(old_file, (old_time, old_time))

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=True, dry_run=False
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        original_exists = Path.exists
        exists_call_count = [0]

        def mock_exists(self):
            exists_call_count[0] += 1
            if exists_call_count[0] == 2 and "subfolder" in str(self):
                return False
            return original_exists(self)

        with patch.object(Path, "exists", mock_exists):
            await coordinator.async_run_cleanup_now()
            await hass.async_block_till_done()

        assert not old_file.exists(), "Old file should still be deleted"
    finally:
        await coordinator.async_shutdown()


async def test_dry_run_directory_would_not_be_empty(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path, caplog
):
    """Test dry run mode when directory would NOT be empty after deletion (line 385)."""
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)

    subdir = media_dir / "subfolder"
    subdir.mkdir()

    old_file = subdir / "old.jpg"
    old_file.write_text("old content")
    new_file = subdir / "new.txt"
    new_file.write_text("new content")

    old_time = time_module.time() - (TEST_FILE_AGE_DAYS * 24 * 60 * 60)
    os.utime(old_file, (old_time, old_time))

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=True, dry_run=True
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        assert old_file.exists(), "Old file should NOT be deleted in dry run"
        assert new_file.exists(), "New file should remain"
        assert (
            subdir.exists()
        ), "Directory should remain because it would still have files"

        log_messages = [record.message.lower() for record in caplog.records]
        has_dir_removal_log = any(
            "dry" in msg
            and "remove" in msg
            and "director" in msg
            and "subfolder" in msg
            for msg in log_messages
        )
        assert (
            not has_dir_removal_log
        ), "Should NOT log directory removal when it wouldn't be empty"
    finally:
        await coordinator.async_shutdown()


async def test_dry_run_parent_already_in_removed_this_round(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path, caplog
):
    """Test dry run mode when parent directory is already in removed_this_round (line 400)."""
    import logging

    caplog.set_level(logging.DEBUG)

    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)

    parent = media_dir / "parent"
    parent.mkdir()
    child1 = parent / "child1"
    child1.mkdir()
    child2 = parent / "child2"
    child2.mkdir()

    file1 = child1 / "old1.jpg"
    file1.write_text("old content 1")
    file2 = child2 / "old2.jpg"
    file2.write_text("old content 2")

    old_time = time_module.time() - (TEST_FILE_AGE_DAYS * 24 * 60 * 60)
    os.utime(file1, (old_time, old_time))
    os.utime(file2, (old_time, old_time))

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=True, dry_run=True
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        assert file1.exists(), "File 1 should NOT be deleted in dry run"
        assert file2.exists(), "File 2 should NOT be deleted in dry run"
        assert child1.exists(), "Child1 should remain in dry run"
        assert child2.exists(), "Child2 should remain in dry run"
        assert parent.exists(), "Parent should remain in dry run"

        debug_messages = [
            record.message.lower()
            for record in caplog.records
            if record.levelname == "DEBUG"
        ]
        dry_run_logs = [
            msg for msg in debug_messages if "dry" in msg and "director" in msg
        ]
        assert len(dry_run_logs) >= 2, "Should log dry run for both child directories"
    finally:
        await coordinator.async_shutdown()


async def test_enotempty_error_during_removal(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path, caplog
):
    """Test handling of ENOTEMPTY error (line 418)."""
    import logging

    caplog.set_level(logging.DEBUG)

    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)

    subdir = media_dir / "subfolder"
    subdir.mkdir()
    old_file = subdir / "old.jpg"
    old_file.write_text("old content")

    old_time = time_module.time() - (TEST_FILE_AGE_DAYS * 24 * 60 * 60)
    os.utime(old_file, (old_time, old_time))

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=True, dry_run=False
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        with patch("pathlib.Path.rmdir") as mock_rmdir:
            enotempty_error = OSError(errno.ENOTEMPTY, "Directory not empty")
            enotempty_error.errno = errno.ENOTEMPTY
            mock_rmdir.side_effect = enotempty_error

            await coordinator.async_run_cleanup_now()
            await hass.async_block_till_done()

            assert not old_file.exists(), "Old file should still be deleted"

            debug_messages = [
                record.message.lower()
                for record in caplog.records
                if record.levelname == "DEBUG"
            ]
            has_enotempty_log = any(
                "not empty" in msg and "race" in msg for msg in debug_messages
            )
            assert (
                has_enotempty_log
            ), "Should log ENOTEMPTY as race condition at DEBUG level"
    finally:
        await coordinator.async_shutdown()


async def test_generic_oserror_during_removal(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path, caplog
):
    """Test handling of generic OSError (line 422)."""
    import logging

    caplog.set_level(logging.WARNING)

    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)

    subdir = media_dir / "subfolder"
    subdir.mkdir()
    old_file = subdir / "old.jpg"
    old_file.write_text("old content")

    old_time = time_module.time() - (TEST_FILE_AGE_DAYS * 24 * 60 * 60)
    os.utime(old_file, (old_time, old_time))

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=True, dry_run=False
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        with patch("pathlib.Path.rmdir") as mock_rmdir:
            generic_error = OSError(errno.EIO, "Input/output error")
            generic_error.errno = errno.EIO
            mock_rmdir.side_effect = generic_error

            await coordinator.async_run_cleanup_now()
            await hass.async_block_till_done()

            assert not old_file.exists(), "Old file should still be deleted"

            warning_messages = [
                record.message.lower()
                for record in caplog.records
                if record.levelname == "WARNING"
            ]
            has_generic_error_log = any(
                "failed to remove" in msg or "input/output" in msg
                for msg in warning_messages
            )
            assert has_generic_error_log, "Should log generic OSError at WARNING level"
    finally:
        await coordinator.async_shutdown()


async def test_dry_run_with_subdirectory_containing_directory(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path
):
    """Test dry run properly handles directories containing other directories."""
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)

    level1 = media_dir / "level1"
    level1.mkdir()
    level2 = level1 / "level2"
    level2.mkdir()
    level3 = level2 / "level3"
    level3.mkdir()

    old_file = level3 / "old.jpg"
    old_file.write_text("old content")

    old_time = time_module.time() - (TEST_FILE_AGE_DAYS * 24 * 60 * 60)
    os.utime(old_file, (old_time, old_time))

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=True, dry_run=True
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        assert old_file.exists(), "File should NOT be deleted in dry run"
        assert level3.exists(), "Level3 should remain in dry run"
        assert level2.exists(), "Level2 should remain in dry run"
        assert level1.exists(), "Level1 should remain in dry run"
    finally:
        await coordinator.async_shutdown()
