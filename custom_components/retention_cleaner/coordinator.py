from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, time as dt_time, timedelta
import errno
import logging
from pathlib import Path
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ALL_FILES_PATTERN,
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
    COORDINATOR_UPDATE_INTERVAL_SECONDS,
    DEFAULT_KEEP_MINIMUM_FILES,
    DEFAULT_MAX_FILES_IN_FOLDER,
    DEFAULT_REMOVE_EMPTY_FOLDERS,
)

_LOGGER = logging.getLogger(__name__)

# Transient errors that should trigger retry
TRANSIENT_ERRORS = {
    errno.EAGAIN,  # Resource temporarily unavailable
    errno.EBUSY,  # Resource busy
    errno.EINTR,  # Interrupted system call
}


@dataclass
class ScanResult:
    """Result data from a folder scan operation.

    Attributes:
        total_files: Total number of files matching the pattern.
        older_than_retention: Number of files older than retention period.
        path_available: Whether the base path exists and is accessible.
        total_size_bytes: Total size in bytes of all matched files.
        older_than_retention_size_bytes: Total size in bytes of files older than retention.
    """

    total_files: int
    older_than_retention: int
    path_available: bool
    total_size_bytes: int = 0
    older_than_retention_size_bytes: int = 0


@dataclass
class CleanupResult:
    """Result data from a cleanup operation.

    Attributes:
        deleted: Number of files successfully deleted.
        total_after: Total files remaining after cleanup.
        older_remaining: Files older than retention that were not deleted.
        path_available: Whether the base path exists and is accessible.
        deleted_bytes: Total size of deleted files in bytes.
    """

    deleted: int
    total_after: int
    older_remaining: int
    path_available: bool
    deleted_bytes: int = 0


@dataclass(frozen=True)
class ConfigSnapshot:
    """Immutable snapshot of coordinator configuration at a point in time.

    This frozen dataclass ensures that configuration values used during
    a cleanup or scan operation remain consistent throughout the entire
    operation, even if the configuration is updated via config entities
    while the operation is in progress.

    Attributes:
        base_path: Absolute path to the monitored folder.
        pattern: Glob pattern for matching files (e.g., "*.jpg").
        retention_days: Number of days to retain files.
        dry_run: If True, simulate operations without making changes.
        max_deletes: Maximum number of files to delete in one run.
        run_at: Time string for daily scheduled cleanup (HH:MM format).
        only_extensions: Comma-separated list of extensions to exclusively process.
        except_extensions: Comma-separated list of extensions to exclude.
        keep_minimum_files: Minimum number of newest files to always preserve.
        max_files_in_folder: Maximum number of files to keep (0 = disabled).
        remove_empty_folders: If True, remove empty directories after cleanup.
    """

    base_path: str
    pattern: str
    retention_days: int
    dry_run: bool
    max_deletes: int
    run_at: str
    only_extensions: str
    except_extensions: str
    keep_minimum_files: int
    max_files_in_folder: int
    remove_empty_folders: bool


def _now() -> datetime:
    """Generate current timestamp with UTC timezone.

    Returns:
        datetime: Current datetime object with UTC timezone.

    Example:
        >>> _now()
        datetime.datetime(2024, 1, 2, 15, 30, 45, tzinfo=timezone.utc)
    """
    return datetime.now(UTC)


async def _retry_async_operation(func, *args, max_retries: int = 3, delay: float = 0.5):
    """Retry an async operation for transient errors.

    Args:
        func: Async function to retry.
        *args: Arguments to pass to the function.
        max_retries: Maximum number of retry attempts.
        delay: Initial delay between retries (doubles each attempt).

    Returns:
        Result from the function.

    Raises:
        The last exception if all retries fail.
    """
    for attempt in range(max_retries):
        try:
            return await func(*args)
        except OSError as e:
            if (
                hasattr(e, "errno")
                and e.errno in TRANSIENT_ERRORS
                and attempt < max_retries - 1
            ):
                wait_time = delay * (2**attempt)
                _LOGGER.debug(
                    "Transient error (errno %d), retrying in %.1fs (attempt %d/%d): %s",
                    e.errno,
                    wait_time,
                    attempt + 1,
                    max_retries,
                    str(e),
                )
                await asyncio.sleep(wait_time)
                continue
            raise


def _parse_run_at(value: str) -> dt_time:
    """Parse time string into datetime.time object.

    Args:
        value: Time string in HH:MM format. Defaults to "03:15" if empty.

    Returns:
        dt_time: Parsed time object with hour, minute, and zero seconds.

    Example:
        >>> _parse_run_at("14:30")
        datetime.time(14, 30, 0)
    """
    hh, mm = (value or "03:15").split(":")
    return dt_time(hour=int(hh), minute=int(mm), second=0)


def _parse_extensions(value: str) -> set[str]:
    """Parse comma-separated extension list into a set.

    Args:
        value: Comma-separated extension list (e.g., ".mp4,.jpg,.MP4")

    Returns:
        set[str]: Set of lowercase extensions for efficient lookup.

    Example:
        >>> _parse_extensions(".mp4,.jpg,.MP4")
        {'.mp4', '.jpg'}
    """
    if not value:
        return set()

    # Parse, strip, filter empty, and convert to lowercase
    extensions = [ext.strip().lower() for ext in value.split(",")]
    return {ext for ext in extensions if ext}


def _should_filter_by_extension(
    file_suffix: str,
    only_ext_set: set[str],
    except_ext_set: set[str],
) -> bool:
    """Check if file should be filtered out based on extension filters.

    Args:
        file_suffix: File extension including dot (e.g., ".mp4")
        only_ext_set: Set of extensions to exclusively process (lowercase)
        except_ext_set: Set of extensions to exclude (lowercase)

    Returns:
        bool: True if file should be filtered out (skipped), False otherwise

    Example:
        >>> _should_filter_by_extension(".mp4", {".mp4", ".jpg"}, set())
        False  # File matches "only" list, process it
        >>> _should_filter_by_extension(".mkv", {".mp4", ".jpg"}, set())
        True  # File not in "only" list, skip it
        >>> _should_filter_by_extension(".log", set(), {".log", ".tmp"})
        True  # File in "except" list, skip it
    """
    file_ext = file_suffix.lower()

    if only_ext_set:
        return file_ext not in only_ext_set
    elif except_ext_set:
        return file_ext in except_ext_set

    return False


def _scan_folder(
    base_path: str,
    pattern: str,
    retention_days: int,
    only_ext_set: set[str] | None = None,
    except_ext_set: set[str] | None = None,
) -> ScanResult:
    """Scan folder and count files based on retention criteria.

    This function performs a non-destructive scan to analyze files
    matching the given pattern and determine how many are older
    than the retention period.

    Args:
        base_path: Absolute path to the folder to scan.
        pattern: Glob pattern to match files (e.g., "*.jpg", "**/*.log").
                 Empty when using extension filters.
        retention_days: Number of days to retain files.
        only_ext_set: Set of extensions to exclusively delete (lowercase with dots).
        except_ext_set: Set of extensions to never delete (lowercase with dots).

    Returns:
        ScanResult: Contains total files, files older than retention,
                   and path availability status.

    Raises:
        RuntimeError: For permission errors on directory access or unexpected errors.

    Note:
        - Files that disappear during scan (race condition) are not counted.
        - Files without read permission are counted but age is unknown.
        - Other OS errors are logged but don't stop the scan.
        - Extension matching is case-insensitive.
    """
    base = Path(base_path)

    # Normalize None to empty set
    only_ext_set = only_ext_set or set()
    except_ext_set = except_ext_set or set()

    # Determine search pattern
    if only_ext_set or except_ext_set:
        search_pattern = ALL_FILES_PATTERN
        _LOGGER.debug(
            "Starting scan of %s with extension filter (only=%d exts, except=%d exts, retention: %d days)",
            base_path,
            len(only_ext_set),
            len(except_ext_set),
            retention_days,
        )
    else:
        # Safety check: ensure pattern is not empty
        if not pattern:
            raise ValueError(
                "No filter configured: pattern is empty and no extension filters provided"
            )
        search_pattern = pattern
        _LOGGER.debug(
            "Starting scan of %s with pattern '%s' (retention: %d days)",
            base_path,
            pattern,
            retention_days,
        )

    if not base.exists() or not base.is_dir():
        _LOGGER.warning("Path not accessible or not a directory: %s", base_path)
        return ScanResult(
            total_files=0,
            older_than_retention=0,
            path_available=False,
            total_size_bytes=0,
            older_than_retention_size_bytes=0,
        )

    cutoff_ts = datetime.now(UTC).timestamp() - (retention_days * 24 * 60 * 60)

    total = 0
    older = 0
    total_size = 0
    older_size = 0

    try:
        for p in base.glob(search_pattern):
            if not p.is_file():
                continue

            # Extension filtering (case-insensitive)
            if _should_filter_by_extension(p.suffix, only_ext_set, except_ext_set):
                continue

            total += 1
            try:
                stat_info = p.stat()  # Get stat once for both mtime and size
                total_size += stat_info.st_size
                if stat_info.st_mtime < cutoff_ts:
                    older += 1
                    older_size += stat_info.st_size
            except FileNotFoundError:
                # Race condition: file was deleted between glob and stat
                _LOGGER.debug(
                    "File disappeared during scan (race condition): %s", p.name
                )
                total -= 1  # Don't count files that no longer exist
                # Don't add to size counters - file doesn't exist
            except PermissionError as err:
                _LOGGER.warning("No permission to access file %s: %s", p.name, err)
                # Keep file counted but can't check age or size
                # Don't add to size counters - can't determine size
            except OSError as err:
                # Other OS errors (network issues, etc)
                _LOGGER.debug("Cannot stat file %s: %s", p.name, err)
                # Keep file counted but can't check age or size
                # Don't add to size counters - can't determine size
    except PermissionError as e:
        _LOGGER.error("No permission to access directory %s: %s", base_path, str(e))
        raise RuntimeError(f"Permission denied accessing {base_path}") from e
    except Exception as e:
        _LOGGER.error("Unexpected error during scan of %s: %s", base_path, str(e))
        raise RuntimeError(f"Scan failed: {e!s}") from e

    _LOGGER.debug(
        "Scan complete for %s: %d total files (%d bytes), %d older than %d days (%d bytes)",
        base_path,
        total,
        total_size,
        older,
        retention_days,
        older_size,
    )
    return ScanResult(
        total_files=total,
        older_than_retention=older,
        path_available=True,
        total_size_bytes=total_size,
        older_than_retention_size_bytes=older_size,
    )


def _remove_empty_directories(
    base_path: str,
    deleted_file_paths: set[Path],
    dry_run: bool,
) -> int:
    """Remove empty directories after file cleanup (bottom-up).

    Args:
        base_path: Base path boundary (never remove this).
        deleted_file_paths: Set of deleted file paths.
        dry_run: If True, log but don't actually remove.

    Returns:
        Number of directories removed.

    Algorithm:
        1. Extract unique parent directories from deleted_file_paths
        2. Iteratively check and remove empty directories bottom-up
        3. After removing a directory, add its parent to the check list
        4. Continue until no more empty directories are found

    Safety:
        - Never removes base_path itself
        - Only removes directories within base_path
        - Preserves directories with hidden files
        - Respects dry_run mode
        - Handles race conditions gracefully
    """
    base_path_obj = Path(base_path)
    removed_dirs = 0

    # Extract parent directories from deleted files
    dirs_to_check = {p.parent for p in deleted_file_paths}

    # Filter out base_path itself
    dirs_to_check = {d for d in dirs_to_check if d != base_path_obj}

    # Iteratively remove empty directories bottom-up
    while dirs_to_check:
        # Sort by depth (deepest first) for bottom-up removal
        sorted_dirs = sorted(dirs_to_check, key=lambda p: len(p.parts), reverse=True)

        # Track which directories were actually removed this iteration
        removed_this_round = set()

        for dir_path in sorted_dirs:
            # Skip if already processed in this round
            if dir_path in removed_this_round:
                continue

            try:
                # Check if directory exists (race condition tolerance)
                if not dir_path.exists():
                    continue

                # Check if directory is empty or would be empty after deletion
                # In dry run mode, files haven't been deleted yet, so check if all remaining
                # files in the directory are in the deleted_file_paths set
                remaining_items = list(dir_path.iterdir())

                if dry_run:
                    # In dry run, check if directory WOULD be empty (all files scheduled for deletion)
                    would_be_empty = all(
                        item in deleted_file_paths or item.is_dir()
                        for item in remaining_items
                    )
                    if not would_be_empty:
                        # Directory would still have files, skip it
                        continue
                else:
                    # In normal mode, check if directory IS empty now
                    if remaining_items:
                        # Directory not empty, skip it
                        continue

                # Directory is empty (or would be empty in dry run) - remove it (respect dry_run)
                if dry_run:
                    _LOGGER.debug(
                        "[DRY-RUN] Would remove empty directory: %s", dir_path
                    )
                    removed_this_round.add(dir_path)

                    # In dry run, also check parent directory
                    parent = dir_path.parent
                    if parent != base_path_obj and parent not in removed_this_round:
                        dirs_to_check.add(parent)
                else:
                    dir_path.rmdir()
                    removed_dirs += 1
                    removed_this_round.add(dir_path)
                    _LOGGER.debug("Removed empty directory: %s", dir_path)

                    # Add parent directory to check if it's now empty
                    parent = dir_path.parent
                    if parent != base_path_obj and parent not in removed_this_round:
                        dirs_to_check.add(parent)

            except FileNotFoundError:
                # Already removed (race condition) - count as success
                removed_dirs += 1
                removed_this_round.add(dir_path)
            except OSError as err:
                if err.errno == errno.ENOTEMPTY:
                    _LOGGER.debug("Directory not empty (race condition): %s", dir_path)
                elif err.errno == errno.EACCES:
                    _LOGGER.warning(
                        "Permission denied removing directory: %s", dir_path
                    )
                else:
                    _LOGGER.warning("Failed to remove directory %s: %s", dir_path, err)

        # Remove processed directories from the check list
        dirs_to_check -= removed_this_round

        # If we didn't remove anything this round, no point continuing
        if not removed_this_round:
            break

    return removed_dirs


def _cleanup_folder(
    base_path: str,
    pattern: str,
    retention_days: int,
    dry_run: bool,
    max_deletes: int,
    only_ext_set: set[str] | None = None,
    except_ext_set: set[str] | None = None,
    keep_minimum_files: int = 0,
    max_files_in_folder: int = 0,
    remove_empty_folders: bool = False,
) -> CleanupResult:
    """Delete files older than retention period with safety limits.

    Performs actual file deletion based on retention criteria,
    respecting dry-run mode and maximum delete limits for safety.

    Order of operations:
        1. Time-based cleanup (retention_days) happens first
        2. File count enforcement (max_files_in_folder) happens second on remaining files
        3. Empty directory removal (if enabled) happens after file deletion

    Args:
        base_path: Absolute path to the folder to clean.
        pattern: Glob pattern to match files (e.g., "*.jpg").
                 Empty when using extension filters.
        retention_days: Number of days to retain files.
        dry_run: If True, simulate deletion without actually deleting.
        max_deletes: Maximum number of files to delete in one run.
        only_ext_set: Set of extensions to exclusively delete (lowercase with dots).
        except_ext_set: Set of extensions to never delete (lowercase with dots).
        keep_minimum_files: Minimum number of newest files to always preserve.
        max_files_in_folder: Maximum number of files to keep (0 = disabled).
        remove_empty_folders: If True, remove empty directories after file deletion.

    Returns:
        CleanupResult: Contains number of deleted files, remaining files,
                      files still older than retention, and path status.

    Raises:
        RuntimeError: For disk full, read-only filesystem, permission errors,
                     or unexpected errors during cleanup.

    Safety:
        - Always preserves the newest keep_minimum_files files regardless of age.
        - Protected files are excluded from deletion candidates BEFORE max_deletes is applied.
        - Respects max_deletes limit to prevent accidental mass deletion.
        - Dry-run mode allows safe preview of what would be deleted.
        - Files already deleted (race condition) are counted as success.
        - Permission errors on individual files are logged but don't stop cleanup.
        - Critical errors (disk full, read-only FS) abort the operation.
        - Extension matching is case-insensitive.
        - max_files_in_folder takes priority over keep_minimum_files.
        - Empty directory removal respects dry_run and never removes base_path.
    """
    base = Path(base_path)

    # Normalize None to empty set
    only_ext_set = only_ext_set or set()
    except_ext_set = except_ext_set or set()

    # Determine search pattern
    if only_ext_set or except_ext_set:
        search_pattern = ALL_FILES_PATTERN
        _LOGGER.debug(
            "Starting cleanup of %s with extension filter (only=%d exts, except=%d exts, retention: %d days, dry_run: %s, max_deletes: %d, keep_minimum: %d, max_files: %d, remove_empty: %s)",
            base_path,
            len(only_ext_set),
            len(except_ext_set),
            retention_days,
            dry_run,
            max_deletes,
            keep_minimum_files,
            max_files_in_folder,
            remove_empty_folders,
        )
    else:
        # Safety check: ensure pattern is not empty
        if not pattern:
            raise ValueError(
                "No filter configured: pattern is empty and no extension filters provided"
            )
        search_pattern = pattern
        _LOGGER.debug(
            "Starting cleanup of %s with pattern '%s' (retention: %d days, dry_run: %s, max_deletes: %d, keep_minimum: %d, max_files: %d, remove_empty: %s)",
            base_path,
            pattern,
            retention_days,
            dry_run,
            max_deletes,
            keep_minimum_files,
            max_files_in_folder,
            remove_empty_folders,
        )

    if not base.exists() or not base.is_dir():
        _LOGGER.warning("Path not accessible or not a directory: %s", base_path)
        return CleanupResult(
            deleted=0,
            total_after=0,
            older_remaining=0,
            path_available=False,
            deleted_bytes=0,
        )

    cutoff_ts = datetime.now(UTC).timestamp() - (retention_days * 24 * 60 * 60)

    deleted = 0
    deleted_bytes = 0
    total_after = 0
    older_remaining = 0

    try:
        # Step 1: Collect all matching files with metadata
        files_with_metadata: list[tuple[Path, float, int]] = []
        inaccessible_files = 0
        deleted_files: set[Path] = set()  # Track which files were actually deleted

        for p in base.glob(search_pattern):
            if not p.is_file():
                continue

            # Extension filtering (case-insensitive)
            if _should_filter_by_extension(p.suffix, only_ext_set, except_ext_set):
                continue

            try:
                # Get file stats (mtime and size) in one call for efficiency
                file_stat = p.stat()
                files_with_metadata.append((p, file_stat.st_mtime, file_stat.st_size))
            except FileNotFoundError:
                # Race condition: file was deleted between glob and stat
                _LOGGER.debug(
                    "File disappeared before processing (race condition): %s", p.name
                )
                continue  # Don't count files that no longer exist
            except PermissionError as err:
                _LOGGER.warning("No permission to access file %s: %s", p.name, err)
                inaccessible_files += 1
                continue
            except OSError as err:
                _LOGGER.debug("Cannot stat file %s: %s", p.name, err)
                inaccessible_files += 1
                continue

        # Step 2: Sort by mtime descending (newest first)
        files_with_metadata.sort(key=lambda x: x[1], reverse=True)

        # Step 3: Determine protected files (keep_minimum_files newest)
        protected_count = min(keep_minimum_files, len(files_with_metadata))
        protected_files = {f[0] for f in files_with_metadata[:protected_count]}

        if protected_count > 0:
            _LOGGER.debug(
                "Protecting %d newest files due to keep_minimum_files threshold",
                protected_count,
            )

        # Step 4: Process files for deletion
        for file_path, mtime, file_size in files_with_metadata:
            # Check if file is protected by keep_minimum_files
            if file_path in protected_files:
                total_after += 1
                if mtime < cutoff_ts:
                    older_remaining += 1  # File is old but protected
                continue

            # Check if file is older than retention
            if mtime < cutoff_ts:
                # File is older than retention
                if dry_run:
                    _LOGGER.debug("[DRY-RUN] Would delete: %s", file_path.name)
                    total_after += 1
                    older_remaining += 1
                    deleted_files.add(
                        file_path
                    )  # Track would-be-deleted files for directory removal
                    continue

                if deleted >= max_deletes:
                    if deleted == max_deletes:  # Log once when limit reached
                        _LOGGER.warning(
                            "Reached max deletion limit (%d) during cleanup of %s",
                            max_deletes,
                            base_path,
                        )
                    total_after += 1
                    older_remaining += 1
                    continue

                try:
                    file_path.unlink()
                    deleted += 1
                    deleted_bytes += file_size
                    deleted_files.add(file_path)  # Track deleted files
                    _LOGGER.debug(
                        "Deleted file: %s (size: %d bytes)", file_path.name, file_size
                    )
                except FileNotFoundError:
                    # Race condition: file was already deleted
                    _LOGGER.debug(
                        "File already deleted (race condition): %s", file_path.name
                    )
                    deleted += 1  # Count as successful since goal achieved
                    deleted_files.add(file_path)  # Track as deleted
                except PermissionError as err:
                    _LOGGER.warning(
                        "No permission to delete file %s: %s", file_path.name, err
                    )
                    total_after += 1
                    older_remaining += 1
                except OSError as err:
                    if err.errno == errno.ENOSPC:
                        _LOGGER.error("Disk full - cannot complete cleanup operation")
                        raise RuntimeError("Disk full") from err
                    elif err.errno == errno.EROFS:
                        _LOGGER.error("Read-only filesystem - cannot delete files")
                        raise RuntimeError("Filesystem is read-only") from err
                    else:
                        _LOGGER.warning(
                            "Failed to delete file %s: [errno %d] %s",
                            file_path.name,
                            err.errno or 0,
                            err,
                        )
                        total_after += 1
                        older_remaining += 1
            else:
                # File is within retention period
                total_after += 1

        # Add inaccessible files to total_after
        total_after += inaccessible_files

        # Step 5: Enforce max_files_in_folder limit on remaining files
        if max_files_in_folder > 0 and total_after > max_files_in_folder:
            files_to_delete_for_count = total_after - max_files_in_folder

            _LOGGER.debug(
                "File count (%d) exceeds max_files_in_folder (%d), need to delete %d more files",
                total_after,
                max_files_in_folder,
                files_to_delete_for_count,
            )

            # Build list of remaining files (not yet deleted)
            remaining_files: list[tuple[Path, float, int]] = []
            for file_path, mtime, file_size in files_with_metadata:
                # Skip files already deleted in Step 4
                if file_path in deleted_files:
                    continue  # Already deleted in Step 4

                # All other files remain (protected, within retention, or hit max_deletes)
                remaining_files.append((file_path, mtime, file_size))

            # Sort remaining files by mtime ascending (oldest first for deletion)
            remaining_files.sort(key=lambda x: x[1])

            # Delete oldest files to reach max_files_in_folder limit
            files_deleted_for_count = 0
            for file_path, mtime, file_size in remaining_files:
                if total_after <= max_files_in_folder:
                    break  # Reached target

                if deleted >= max_deletes:
                    if deleted == max_deletes:  # Log once
                        _LOGGER.warning(
                            "Reached max deletion limit (%d) during file count enforcement",
                            max_deletes,
                        )
                    break  # Safety limit reached

                if dry_run:
                    _LOGGER.debug(
                        "[DRY-RUN] Would delete for file count limit: %s",
                        file_path.name,
                    )
                    deleted_files.add(file_path)  # Track would-be-deleted files
                    # Don't modify counters in dry run
                    continue

                try:
                    file_path.unlink()
                    deleted += 1
                    deleted_bytes += file_size
                    total_after -= 1
                    files_deleted_for_count += 1
                    deleted_files.add(file_path)  # Track deleted files
                    # Update older_remaining if this was an old file
                    if mtime < cutoff_ts:
                        older_remaining -= 1
                    _LOGGER.debug(
                        "Deleted for file count limit: %s (size: %d bytes)",
                        file_path.name,
                        file_size,
                    )
                except FileNotFoundError:
                    # Race condition: already deleted
                    _LOGGER.debug(
                        "File already deleted (race condition): %s", file_path.name
                    )
                    deleted += 1
                    total_after -= 1
                    files_deleted_for_count += 1
                    deleted_files.add(file_path)  # Track as deleted
                    # Update older_remaining if this was an old file
                    if mtime < cutoff_ts:
                        older_remaining -= 1
                except PermissionError as err:
                    _LOGGER.warning(
                        "No permission to delete file %s: %s", file_path.name, err
                    )
                except OSError as err:
                    if err.errno == errno.ENOSPC:
                        _LOGGER.error("Disk full - cannot complete cleanup operation")
                        raise RuntimeError("Disk full") from err
                    elif err.errno == errno.EROFS:
                        _LOGGER.error("Read-only filesystem - cannot delete files")
                        raise RuntimeError("Filesystem is read-only") from err
                    else:
                        _LOGGER.warning(
                            "Failed to delete file %s: [errno %d] %s",
                            file_path.name,
                            err.errno or 0,
                            err,
                        )

            if files_deleted_for_count > 0:
                _LOGGER.debug(
                    "Deleted %d files to enforce max_files_in_folder=%d limit",
                    files_deleted_for_count,
                    max_files_in_folder,
                )

        # Step 6: Remove empty directories if enabled
        if remove_empty_folders and deleted_files:
            removed_dirs = _remove_empty_directories(base_path, deleted_files, dry_run)
            if removed_dirs > 0:
                _LOGGER.debug("Removed %d empty directories", removed_dirs)

    except PermissionError as e:
        _LOGGER.error("No permission to access directory %s: %s", base_path, str(e))
        raise RuntimeError(f"Permission denied accessing {base_path}") from e
    except RuntimeError:
        # Re-raise RuntimeError from disk full/read-only checks
        raise
    except Exception as e:
        _LOGGER.error("Unexpected error during cleanup of %s: %s", base_path, str(e))
        raise RuntimeError(f"Cleanup failed: {e!s}") from e

    _LOGGER.debug(
        "Cleanup complete for %s: deleted %d files (%d bytes), %d files remaining (%d older than retention)",
        base_path,
        deleted,
        deleted_bytes,
        total_after,
        older_remaining,
    )
    return CleanupResult(
        deleted=deleted,
        total_after=total_after,
        older_remaining=older_remaining,
        path_available=True,
        deleted_bytes=deleted_bytes,
    )


class RetentionCleanerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for managing retention-based file cleanup operations.

    This coordinator handles both manual and scheduled cleanup operations,
    maintains state for UI sensors, and manages the lifecycle of scheduled
    tasks. It extends Home Assistant's DataUpdateCoordinator to provide
    regular updates to connected entities.

    Attributes:
        hass: Home Assistant instance.
        entry: Config entry containing user configuration.
        deleted_last_run: Number of files deleted in the last cleanup.
        last_scan: Datetime of the last scan operation.
        last_cleanup: Datetime of the last cleanup operation.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the retention cleaner coordinator.

        Args:
            hass: Home Assistant instance for integration.
            entry: Configuration entry with user settings.
        """
        self.hass = hass
        self.entry = entry

        # Visible runtime state for dashboard (separated!)
        self.deleted_last_run: int = 0
        self.deleted_bytes_last_run: int = 0
        self.last_scan: datetime | None = None
        self.last_cleanup: datetime | None = None
        self.last_scan_duration_ms: int = 0
        self.last_cleanup_duration_ms: int = 0

        self._unsub_daily = None

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"retention_cleaner_{entry.entry_id}",
            update_interval=timedelta(seconds=COORDINATOR_UPDATE_INTERVAL_SECONDS),
        )

    @property
    def cfg(self) -> dict[str, Any]:
        """Get merged configuration from entry data and options.

        Returns:
            dict[str, Any]: Combined configuration dictionary with
                           options overriding data values.
        """
        return {**self.entry.data, **self.entry.options}

    @property
    def base_path(self) -> str:
        """Get the base path for file operations.

        Returns:
            str: Absolute path to the monitored folder.
        """
        return self.cfg[CONF_BASE_PATH]

    @property
    def pattern(self) -> str:
        """Get the file matching pattern.

        Returns:
            str: Glob pattern for matching files (e.g., "*.jpg").
        """
        return self.cfg.get(CONF_PATTERN, "")

    @property
    def only_extensions(self) -> str:
        """Get the only_extensions filter.

        Returns:
            str: Comma-separated list of extensions to exclusively delete.
        """
        return self.cfg.get(CONF_ONLY_EXTENSIONS, "")

    @property
    def except_extensions(self) -> str:
        """Get the except_extensions filter.

        Returns:
            str: Comma-separated list of extensions to never delete.
        """
        return self.cfg.get(CONF_EXCEPT_EXTENSIONS, "")

    @property
    def only_extensions_set(self) -> set[str]:
        """Get parsed set of only_extensions for efficient lookup.

        Returns:
            set[str]: Lowercase extension set from only_extensions config
        """
        return _parse_extensions(self.only_extensions)

    @property
    def except_extensions_set(self) -> set[str]:
        """Get parsed set of except_extensions for efficient lookup.

        Returns:
            set[str]: Lowercase extension set from except_extensions config
        """
        return _parse_extensions(self.except_extensions)

    @property
    def retention_days(self) -> int:
        """Get the retention period in days.

        Returns:
            int: Number of days to retain files before deletion.
        """
        return int(self.cfg[CONF_RETENTION_DAYS])

    @property
    def dry_run(self) -> bool:
        """Check if dry-run mode is enabled.

        Returns:
            bool: True if deletions should be simulated only.
        """
        # Check for test override first (allows direct assignment in tests)
        if hasattr(self, "_test_dry_run"):
            return self._test_dry_run

        # Check for cached dry_run value (set by async_update_config_value)
        # This ensures immediate availability after config updates
        if hasattr(self, "_cached_dry_run"):
            return self._cached_dry_run

        return bool(self.cfg.get(CONF_DRY_RUN, False))

    @dry_run.setter
    def dry_run(self, value: bool) -> None:
        """Set dry-run mode (for testing purposes only).

        Args:
            value: True to enable dry-run mode, False to disable.
        """
        self._test_dry_run = value

    @property
    def max_deletes(self) -> int:
        """Get maximum number of files to delete per run.

        Returns:
            int: Maximum deletion limit (default: 5000).
        """
        return int(self.cfg.get(CONF_MAX_DELETES, 5000))

    @property
    def keep_minimum_files(self) -> int:
        """Get minimum number of files to always keep.

        Returns:
            int: Minimum file threshold (default: 0).
        """
        return int(self.cfg.get(CONF_KEEP_MINIMUM_FILES, DEFAULT_KEEP_MINIMUM_FILES))

    @property
    def max_files_in_folder(self) -> int:
        """Get maximum number of files allowed in folder.

        Returns:
            int: Maximum file count (0 = disabled, default: 0).
        """
        return int(self.cfg.get(CONF_MAX_FILES_IN_FOLDER, DEFAULT_MAX_FILES_IN_FOLDER))

    @property
    def remove_empty_folders(self) -> bool:
        """Check if empty folder removal is enabled.

        Returns:
            bool: True if empty directories should be removed after cleanup.
        """
        # Check for test override first (allows direct assignment in tests)
        if hasattr(self, "_test_remove_empty_folders"):
            return self._test_remove_empty_folders

        return bool(
            self.cfg.get(CONF_REMOVE_EMPTY_FOLDERS, DEFAULT_REMOVE_EMPTY_FOLDERS)
        )

    @remove_empty_folders.setter
    def remove_empty_folders(self, value: bool) -> None:
        """Set remove empty folders mode (for testing purposes only).

        Args:
            value: True to enable empty folder removal, False to disable.
        """
        self._test_remove_empty_folders = value

    @property
    def run_at(self) -> dt_time:
        """Get the scheduled daily cleanup time.

        Returns:
            dt_time: Time of day for scheduled cleanup.
        """
        return _parse_run_at(self.cfg.get(CONF_RUN_AT, "03:15"))

    def create_config_snapshot(self) -> ConfigSnapshot:
        """Create an immutable snapshot of the current configuration.

        Returns:
            ConfigSnapshot: Frozen dataclass containing all config values
                          at the moment this method is called.

        Note:
            This snapshot should be created at the start of cleanup/scan
            operations to ensure consistent configuration throughout the
            operation, even if config entities modify values during execution.
        """
        return ConfigSnapshot(
            base_path=self.base_path,
            pattern=self.pattern,
            retention_days=self.retention_days,
            dry_run=self.dry_run,
            max_deletes=self.max_deletes,
            run_at=self.cfg.get(CONF_RUN_AT, "03:15"),
            only_extensions=self.only_extensions,
            except_extensions=self.except_extensions,
            keep_minimum_files=self.keep_minimum_files,
            max_files_in_folder=self.max_files_in_folder,
            remove_empty_folders=self.remove_empty_folders,
        )

    async def async_setup_daily_schedule(self) -> None:
        """Schedule the daily cleanup run based on config.

        Sets up a daily trigger at the configured time to run
        automated cleanup. Removes any existing schedule first
        to prevent duplicates.

        The scheduled cleanup will run with triggered_by="schedule"
        to distinguish it from manual runs in logs.
        """
        self.async_remove_listeners()

        t = self.run_at
        _LOGGER.info(
            "Setting up daily cleanup schedule for %s at %02d:%02d",
            self.base_path,
            t.hour,
            t.minute,
        )

        @callback
        async def _run_daily(now: datetime) -> None:
            _LOGGER.debug("Scheduled cleanup triggered for %s", self.base_path)
            await self.async_run_cleanup_now(triggered_by="schedule")

        self._unsub_daily = async_track_time_change(
            self.hass,
            _run_daily,
            hour=t.hour,
            minute=t.minute,
            second=0,
        )

    async def async_update_config_value(self, key: str, value: Any) -> None:
        """Update a configuration value and persist it to entry.options.

        This method updates the configuration entry's options dictionary
        with the new value, persists it to storage via Home Assistant's
        config_entries.async_update_entry, and triggers a coordinator
        refresh to apply the new configuration.

        Special handling:
            - When CONF_RUN_AT is updated, async_setup_daily_schedule is
              called to reschedule the daily cleanup with the new time.

        Args:
            key: Configuration key (e.g., CONF_RETENTION_DAYS).
            value: New value to set for the configuration key.

        Example:
            await coordinator.async_update_config_value(CONF_RETENTION_DAYS, 14)
            await coordinator.async_update_config_value(CONF_RUN_AT, "04:30")
        """
        new_options = {**self.entry.options, key: value}

        # Cache the new value for immediate availability (especially for dry_run)
        # This works around timing issues with entry.options property updates
        if key == CONF_DRY_RUN:
            self._cached_dry_run = value
            # Clear test override
            if hasattr(self, "_test_dry_run"):
                delattr(self, "_test_dry_run")
        elif key == CONF_REMOVE_EMPTY_FOLDERS:
            # Clear test override for remove_empty_folders
            if hasattr(self, "_test_remove_empty_folders"):
                delattr(self, "_test_remove_empty_folders")

        self.hass.config_entries.async_update_entry(
            self.entry,
            options=new_options,
        )

        if key == CONF_RUN_AT:
            await self.async_setup_daily_schedule()

        # Dry-run and remove_empty_folders changes don't require a file system scan, just notify entities
        # Other config changes (retention_days, pattern, etc.) need a rescan
        if key in (CONF_DRY_RUN, CONF_REMOVE_EMPTY_FOLDERS):
            # Manually notify all coordinator entities to update their state
            self.async_update_listeners()
        else:
            # Request refresh and wait for it to complete
            # This ensures entities read the updated config values
            await self.async_request_refresh()

    def async_remove_listeners(self) -> None:
        """Remove scheduler listeners (called on unload).

        Cleanly removes any active schedule listeners to prevent
        orphaned tasks when the integration is unloaded or reloaded.
        """
        if self._unsub_daily:
            _LOGGER.debug("Removing daily schedule for %s", self.base_path)
            self._unsub_daily()
            self._unsub_daily = None

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and clean up resources.

        This method should be called when the coordinator is no longer needed
        to prevent lingering timers and clean up resources properly.
        """
        _LOGGER.debug("Shutting down coordinator for %s", self.base_path)
        self.async_remove_listeners()

        # Call parent shutdown if available
        if hasattr(super(), "async_shutdown"):
            await super().async_shutdown()

    async def async_run_scan_now(self) -> None:
        """Manually trigger a scan operation.

        Performs a non-destructive scan to update file counts
        and statistics without deleting any files. Updates the
        last_scan timestamp and refreshes coordinator data.

        This method is typically called from the UI button entity.
        """
        """Manual scan refresh (no deletion)."""
        _LOGGER.debug("Manual scan triggered for %s", self.base_path)
        self.last_scan = _now()
        await self.async_request_refresh()

    async def async_run_cleanup_now(self, triggered_by: str = "manual") -> None:
        """Execute cleanup operation to delete old files.

        Performs file deletion for files older than the retention period,
        respecting dry-run mode and max_deletes limit. Updates statistics
        and refreshes coordinator data after cleanup.

        Args:
            triggered_by: Source of trigger ("manual" or "schedule").

        Raises:
            UpdateFailed: If the cleanup operation fails.

        Note:
            The last_cleanup timestamp is set immediately to provide
            user feedback, even if the operation later fails.
        """
        """Manual or scheduled cleanup run (deletes files older than retention)."""
        _LOGGER.info("Starting cleanup (%s) for %s", triggered_by, self.base_path)
        # Mark intent/time first so the dashboard shows something even if scan later fails
        self.last_cleanup = _now()

        # Measure cleanup duration
        start_time = time.perf_counter()

        try:
            # Use retry logic for cleanup operation
            result: CleanupResult = await _retry_async_operation(
                asyncio.to_thread,
                _cleanup_folder,
                self.base_path,
                self.pattern,
                self.retention_days,
                self.dry_run,
                self.max_deletes,
                self.only_extensions_set,
                self.except_extensions_set,
                self.keep_minimum_files,
                self.max_files_in_folder,
                self.remove_empty_folders,
                max_retries=2,  # Fewer retries for cleanup (safety)
                delay=1.0,  # Longer initial delay
            )
        except RuntimeError as e:
            # Specific runtime errors (disk full, read-only) should not be retried
            _LOGGER.error(
                "Critical error during cleanup: %s (path=%s, pattern=%s, retention_days=%d, dry_run=%s)",
                str(e),
                self.base_path,
                self.pattern,
                self.retention_days,
                self.dry_run,
            )
            raise UpdateFailed(f"Cleanup failed for {self.base_path}: {e}") from e
        except Exception as e:
            # keep last_cleanup timestamp, but expose error via coordinator failure
            _LOGGER.error(
                "Cleanup failed: %s (path=%s, pattern=%s, retention_days=%d, dry_run=%s)",
                str(e),
                self.base_path,
                self.pattern,
                self.retention_days,
                self.dry_run,
            )
            raise UpdateFailed(f"Cleanup failed for {self.base_path}: {e}") from e

        # Calculate and store cleanup duration
        self.last_cleanup_duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Update visible state
        self.deleted_last_run = result.deleted
        self.deleted_bytes_last_run = result.deleted_bytes

        # Refresh counts after cleanup
        await self.async_request_refresh()

        _LOGGER.info(
            "Retention Cleaner cleanup run (%s): deleted=%s dry_run=%s max_deletes=%s base_path=%s",
            triggered_by,
            result.deleted,
            self.dry_run,
            self.max_deletes,
            self.base_path,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest data for coordinator update.

        Called periodically by the DataUpdateCoordinator base class
        to refresh sensor data. Performs a scan operation and returns
        current statistics and configuration.

        Returns:
            dict[str, Any]: Dictionary containing all sensor data including
                          file counts, timestamps, and configuration values.

        Raises:
            UpdateFailed: If the scan operation fails.
        """
        # Any refresh means: we updated the values
        self.last_scan = _now()

        # Measure scan duration
        start_time = time.perf_counter()

        try:
            # Use retry logic for scan operation
            result: ScanResult = await _retry_async_operation(
                asyncio.to_thread,
                _scan_folder,
                self.base_path,
                self.pattern,
                self.retention_days,
                self.only_extensions_set,
                self.except_extensions_set,
                max_retries=3,
                delay=0.5,
            )
        except RuntimeError as e:
            _LOGGER.error(
                "Critical error during scan of %s: %s", self.base_path, str(e)
            )
            raise UpdateFailed(str(e)) from e
        except Exception as e:
            raise UpdateFailed(str(e)) from e

        # Calculate and store scan duration
        self.last_scan_duration_ms = int((time.perf_counter() - start_time) * 1000)

        return {
            "base_path": self.base_path,
            "pattern": self.pattern,
            "only_extensions": self.only_extensions,
            "except_extensions": self.except_extensions,
            "retention_days": self.retention_days,
            "dry_run": self.dry_run,
            "max_deletes": self.max_deletes,
            "keep_minimum_files": self.keep_minimum_files,
            "max_files_in_folder": self.max_files_in_folder,
            "run_at": self.cfg.get(CONF_RUN_AT, "03:15"),
            "path_available": result.path_available,
            "total_files": result.total_files,
            "older_than_retention": result.older_than_retention,
            "deleted_last_run": self.deleted_last_run,
            "deleted_bytes_last_run": self.deleted_bytes_last_run,
            "last_scan": self.last_scan,
            "last_cleanup": self.last_cleanup,
            "last_scan_duration_ms": self.last_scan_duration_ms,
            "last_cleanup_duration_ms": self.last_cleanup_duration_ms,
            "total_folder_size_bytes": result.total_size_bytes,
            "older_than_retention_size_bytes": result.older_than_retention_size_bytes,
        }
