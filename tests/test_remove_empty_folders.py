"""Test the remove empty folders feature (TDD - tests written before implementation)."""

import errno
import os
import time as time_module
from unittest.mock import patch

from homeassistant.core import HomeAssistant
import pytest

from custom_components.retention_cleaner.coordinator import RetentionCleanerCoordinator
from tests.conftest import (
    TEST_DIR_DEPTH_DEEP,
    TEST_DIR_DEPTH_MEDIUM,
    TEST_DIR_DEPTH_SHALLOW,
    TEST_FILE_AGE_DAYS,
    TEST_HIDDEN_FILE_DS_STORE,
    TEST_HIDDEN_FILE_GITKEEP,
    TEST_HIDDEN_FILE_KEEP,
)


async def test_feature_disabled_by_default(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path
):
    """Test that remove_empty_folders defaults to False."""
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)
    empty_dir = media_dir / "empty_folder"
    empty_dir.mkdir()

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=False, dry_run=False
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        assert (
            empty_dir.exists()
        ), "Empty directory should not be removed when feature disabled"
    finally:
        await coordinator.async_shutdown()


async def test_remove_single_empty_directory(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path
):
    """Test removal of a single empty directory after cleanup."""
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
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        assert not old_file.exists(), "Old file should be deleted"
        assert (
            not subdir.exists()
        ), "Empty directory should be removed after file deletion"
        assert media_dir.exists(), "Base path should never be removed"
    finally:
        await coordinator.async_shutdown()


async def test_preserve_directory_with_files(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path
):
    """Test that directories with remaining files are not removed."""
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)

    subdir = media_dir / "subfolder"
    subdir.mkdir()

    old_file = subdir / "old.jpg"
    old_file.write_text("old content")
    new_file = subdir / "new.jpg"
    new_file.write_text("new content")

    old_time = time_module.time() - (TEST_FILE_AGE_DAYS * 24 * 60 * 60)
    os.utime(old_file, (old_time, old_time))

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=True, dry_run=False
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        assert not old_file.exists(), "Old file should be deleted"
        assert new_file.exists(), "New file should remain"
        assert subdir.exists(), "Directory with remaining files should not be removed"
    finally:
        await coordinator.async_shutdown()


@pytest.mark.parametrize(
    "hidden_file_name",
    [
        TEST_HIDDEN_FILE_GITKEEP,
        TEST_HIDDEN_FILE_DS_STORE,
        TEST_HIDDEN_FILE_KEEP,
    ],
)
async def test_preserve_directory_with_hidden_files(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path, hidden_file_name
):
    """Test that directories with hidden files are preserved."""
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)

    subdir = media_dir / "subfolder"
    subdir.mkdir()

    hidden_file = subdir / hidden_file_name
    hidden_file.write_text("keep this directory")

    old_file = subdir / "old.jpg"
    old_file.write_text("old content")

    old_time = time_module.time() - (TEST_FILE_AGE_DAYS * 24 * 60 * 60)
    os.utime(old_file, (old_time, old_time))

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=True, dry_run=False
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        assert not old_file.exists(), "Old file should be deleted"
        assert hidden_file.exists(), "Hidden file should remain"
        assert subdir.exists(), "Directory with hidden file should not be removed"
    finally:
        await coordinator.async_shutdown()


@pytest.mark.parametrize(
    "depth",
    [
        TEST_DIR_DEPTH_SHALLOW,
        TEST_DIR_DEPTH_MEDIUM,
        TEST_DIR_DEPTH_DEEP,
    ],
)
async def test_remove_nested_empty_directories(
    hass: HomeAssistant,
    mock_remove_empty_config,
    tmp_path,
    create_nested_dirs,
    depth,
):
    """Test removal of nested empty directories at various depths."""
    media_dir = tmp_path / "media"
    base_dir, all_dirs = create_nested_dirs(media_dir, depth=depth, files_in_leaf=False)

    deepest_dir = all_dirs[-1]
    old_file = deepest_dir / "old.jpg"
    old_file.write_text("old content")

    old_time = time_module.time() - (TEST_FILE_AGE_DAYS * 24 * 60 * 60)
    os.utime(old_file, (old_time, old_time))

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=True, dry_run=False
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        assert not old_file.exists(), "Old file should be deleted"
        for dir_path in all_dirs:
            assert (
                not dir_path.exists()
            ), f"Empty directory {dir_path.name} should be removed"
        assert media_dir.exists(), "Base path should never be removed"
    finally:
        await coordinator.async_shutdown()


async def test_nested_partial_empty(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path, create_nested_dirs
):
    """Test nested directories where some parents are empty and some are not."""
    media_dir = tmp_path / "media"
    base_dir, all_dirs = create_nested_dirs(
        media_dir, depth=TEST_DIR_DEPTH_MEDIUM, files_in_leaf=False
    )

    middle_dir = all_dirs[1]
    keep_file = middle_dir / "keep.jpg"
    keep_file.write_text("keep content")

    deepest_dir = all_dirs[-1]
    old_file = deepest_dir / "old.jpg"
    old_file.write_text("old content")

    old_time = time_module.time() - (TEST_FILE_AGE_DAYS * 24 * 60 * 60)
    os.utime(old_file, (old_time, old_time))

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=True, dry_run=False
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        assert not old_file.exists(), "Old file should be deleted"
        assert keep_file.exists(), "Keep file should remain"
        assert middle_dir.exists(), "Directory with file should not be removed"
        assert not deepest_dir.exists(), "Empty child directory should be removed"
    finally:
        await coordinator.async_shutdown()


async def test_multiple_branches(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path
):
    """Test removal of multiple parallel directory trees."""
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)

    branch1 = media_dir / "branch1" / "sub1"
    branch1.mkdir(parents=True)
    file1 = branch1 / "old1.jpg"
    file1.write_text("old content 1")

    branch2 = media_dir / "branch2" / "sub2"
    branch2.mkdir(parents=True)
    file2 = branch2 / "old2.jpg"
    file2.write_text("old content 2")

    branch3 = media_dir / "branch3" / "sub3"
    branch3.mkdir(parents=True)
    file3 = branch3 / "old3.jpg"
    file3.write_text("old content 3")
    keep_file = branch3 / "keep.jpg"
    keep_file.write_text("keep content")

    old_time = time_module.time() - (TEST_FILE_AGE_DAYS * 24 * 60 * 60)
    os.utime(file1, (old_time, old_time))
    os.utime(file2, (old_time, old_time))
    os.utime(file3, (old_time, old_time))

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=True, dry_run=False
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        assert not file1.exists(), "Old file 1 should be deleted"
        assert not file2.exists(), "Old file 2 should be deleted"
        assert not file3.exists(), "Old file 3 should be deleted"

        assert not branch1.exists(), "Empty branch1 should be removed"
        assert not (
            media_dir / "branch1"
        ).exists(), "Empty parent of branch1 should be removed"

        assert not branch2.exists(), "Empty branch2 should be removed"
        assert not (
            media_dir / "branch2"
        ).exists(), "Empty parent of branch2 should be removed"

        assert keep_file.exists(), "Keep file should remain"
        assert branch3.exists(), "Branch3 with remaining file should not be removed"
        assert (
            media_dir / "branch3"
        ).exists(), "Parent of branch3 should not be removed"
    finally:
        await coordinator.async_shutdown()


async def test_dry_run_logs_but_not_removes(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path, caplog
):
    """Test that dry run mode logs directory removals but doesn't delete."""
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)

    subdir = media_dir / "subfolder"
    subdir.mkdir()
    old_file = subdir / "old.jpg"
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

        assert old_file.exists(), "Old file should NOT be deleted in dry run mode"
        assert subdir.exists(), "Empty directory should NOT be removed in dry run mode"

        log_messages = [record.message.lower() for record in caplog.records]
        has_dry_run_log = any(
            "dry" in msg
            and ("remove" in msg or "would")
            and ("director" in msg or "folder" in msg)
            for msg in log_messages
        )
        assert has_dry_run_log, "Should log that directory would be removed in dry run"
    finally:
        await coordinator.async_shutdown()


async def test_dry_run_false_actually_removes(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path
):
    """Test that with dry_run=False, directories are actually removed."""
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
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        assert not old_file.exists(), "Old file should be deleted"
        assert (
            not subdir.exists()
        ), "Empty directory should be removed when dry_run=False"
    finally:
        await coordinator.async_shutdown()


async def test_never_remove_base_path(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path
):
    """Test that base_path is never removed, even if all subdirectories are removed."""
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)

    old_file = media_dir / "old.jpg"
    old_file.write_text("old content")

    old_time = time_module.time() - (TEST_FILE_AGE_DAYS * 24 * 60 * 60)
    os.utime(old_file, (old_time, old_time))

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=True, dry_run=False
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        assert not old_file.exists(), "Old file should be deleted"
        assert media_dir.exists(), "Base path must never be removed"
        assert list(media_dir.iterdir()) == [], "Base path should be empty but exist"
    finally:
        await coordinator.async_shutdown()


async def test_only_within_base_path(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path
):
    """Test that only directories within base_path are considered for removal."""
    parent_dir = tmp_path / "parent"
    parent_dir.mkdir(parents=True)

    media_dir = parent_dir / "media"
    media_dir.mkdir()

    old_file = media_dir / "old.jpg"
    old_file.write_text("old content")

    old_time = time_module.time() - (TEST_FILE_AGE_DAYS * 24 * 60 * 60)
    os.utime(old_file, (old_time, old_time))

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=True, dry_run=False
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        assert not old_file.exists(), "Old file should be deleted"
        assert media_dir.exists(), "Base path (media) should not be removed"
        assert (
            parent_dir.exists()
        ), "Parent directory outside base path should not be touched"
    finally:
        await coordinator.async_shutdown()


async def test_directory_becomes_empty_after_file_deletion(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path
):
    """Integration test: directory becomes empty during cleanup operation."""
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)

    subdir1 = media_dir / "folder1"
    subdir1.mkdir()
    subdir2 = media_dir / "folder2"
    subdir2.mkdir()

    old_file1 = subdir1 / "old1.jpg"
    old_file1.write_text("old content 1")
    old_file2 = subdir2 / "old2.jpg"
    old_file2.write_text("old content 2")

    old_time = time_module.time() - (TEST_FILE_AGE_DAYS * 24 * 60 * 60)
    os.utime(old_file1, (old_time, old_time))
    os.utime(old_file2, (old_time, old_time))

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=True, dry_run=False
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        assert not old_file1.exists(), "Old file 1 should be deleted"
        assert not old_file2.exists(), "Old file 2 should be deleted"
        assert not subdir1.exists(), "Empty folder1 should be removed"
        assert not subdir2.exists(), "Empty folder2 should be removed"
        assert media_dir.exists(), "Base path should remain"
    finally:
        await coordinator.async_shutdown()


async def test_permission_error_handled_gracefully(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path, caplog
):
    """Test that permission errors during directory removal are handled gracefully."""
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
            mock_rmdir.side_effect = OSError(errno.EACCES, "Permission denied")

            await coordinator.async_run_cleanup_now()
            await hass.async_block_till_done()

            assert not old_file.exists(), "Old file should still be deleted"

            log_messages = [record.message.lower() for record in caplog.records]
            has_permission_log = any(
                "permission" in msg or "error" in msg for msg in log_messages
            )
            assert (
                has_permission_log or mock_rmdir.called
            ), "Should handle or log permission error"
    finally:
        await coordinator.async_shutdown()


async def test_race_condition_dir_already_removed(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path, caplog
):
    """Test that race condition (directory already removed) is handled gracefully."""
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
            mock_rmdir.side_effect = FileNotFoundError("Directory not found")

            await coordinator.async_run_cleanup_now()
            await hass.async_block_till_done()

            assert not old_file.exists(), "Old file should still be deleted"
            assert mock_rmdir.called, "Should attempt to remove directory"
    finally:
        await coordinator.async_shutdown()


async def test_scan_does_not_trigger_removal(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path
):
    """Test that scan operations do not trigger directory removal."""
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)

    empty_dir = media_dir / "empty_folder"
    empty_dir.mkdir()

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=True, dry_run=False
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        await coordinator.async_run_scan_now()
        await hass.async_block_till_done()

        assert empty_dir.exists(), "Empty directory should not be removed during scan"
    finally:
        await coordinator.async_shutdown()


async def test_logs_at_debug_level(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path, caplog
):
    """Test that directory removals are logged at DEBUG level."""
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
        await coordinator.async_run_cleanup_now()
        await hass.async_block_till_done()

        debug_messages = [
            record.message.lower()
            for record in caplog.records
            if record.levelname == "DEBUG"
        ]
        has_removal_log = any(
            "remov" in msg and ("director" in msg or "folder" in msg)
            for msg in debug_messages
        )
        assert has_removal_log, "Should log directory removal at DEBUG level"
    finally:
        await coordinator.async_shutdown()


async def test_remove_empty_folders_property_test_override(
    hass: HomeAssistant, mock_remove_empty_config, tmp_path
):
    """Test that _test_remove_empty_folders override works correctly.

    This covers the defensive code path in remove_empty_folders property
    that checks for a test override attribute before checking the config.
    """
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True)
    empty_dir = media_dir / "empty_folder"
    empty_dir.mkdir()

    entry = mock_remove_empty_config(
        base_path=str(media_dir), remove_empty=False, dry_run=False
    )
    coordinator = RetentionCleanerCoordinator(hass, entry)

    try:
        assert not coordinator.remove_empty_folders, "Config should disable feature"

        coordinator._test_remove_empty_folders = True
        assert coordinator.remove_empty_folders, "Test override should enable feature"

        coordinator._test_remove_empty_folders = False
        assert (
            not coordinator.remove_empty_folders
        ), "Test override should disable feature"

        delattr(coordinator, "_test_remove_empty_folders")
        assert not coordinator.remove_empty_folders, "Should fall back to config"
    finally:
        await coordinator.async_shutdown()
