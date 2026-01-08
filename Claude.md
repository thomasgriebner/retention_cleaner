# Claude.md – AI Development Guidelines for Retention Cleaner

This document provides comprehensive guidelines for Claude and other AI assistants working on the Retention Cleaner custom integration for Home Assistant. **The primary focus is on safe, cautious development to prevent accidental data loss and ensure system stability.**

---

## Project Overview

**Retention Cleaner** is a Home Assistant custom component that automatically deletes old files based on configurable retention rules. It manages camera recordings, snapshots, logs, and other files in the `/media/` directory.

- **Technology Stack**: Python 3, asyncio, Home Assistant Core APIs
- **Integration Type**: Local file operations with scheduled automation (HACS-compatible)
- **Key Features**: Rule-based cleanup, dry-run mode, safety limits, performance tracking
- **⚠️ CRITICAL**: This integration permanently deletes files from disk

### Core Components

| File | Purpose |
|------|---------|
| `__init__.py` | Integration initialization, platform setup, coordinator lifecycle |
| `config_flow.py` | User configuration flow with path/pattern validation |
| `coordinator.py` | Data update coordinator, file scanning/deletion logic, scheduling |
| `sensor.py` | Sensor entity definitions (file counts, timestamps, performance) |
| `binary_sensor.py` | Path availability monitoring |
| `button.py` | Manual scan/cleanup trigger buttons |
| `const.py` | Constants (defaults, configuration keys) |

---

## ⚠️ CRITICAL SAFETY RULES FOR FILE DELETION

### 1. File Operations Are Permanent

**THIS INTEGRATION DELETES FILES PERMANENTLY.** Extreme caution is required:

- ✅ **DO**: Treat every file operation as irreversible
- ✅ **DO**: Validate paths thoroughly before any deletion
- ✅ **DO**: Respect dry-run mode unconditionally
- ✅ **DO**: Enforce max_deletes safety limit strictly
- ✅ **DO**: Test changes with dry-run mode enabled
- ❌ **DON'T**: Bypass or weaken path validation
- ❌ **DON'T**: Remove safety checks "for performance"
- ❌ **DON'T**: Ignore dry-run mode in any code path
- ❌ **DON'T**: Increase default limits without explicit user request

**Path Restriction:**
- **ONLY** `/media/` paths are allowed (enforced in config_flow)
- This prevents accidental deletion of system files or Home Assistant config
- Never remove or weaken this validation

**Pattern Validation:**
- Block extremely dangerous patterns: `*`, `**/*`
- Check for invalid syntax: unclosed brackets, triple asterisks
- These patterns could match ALL files in a directory

### 2. File System Safety

**ALWAYS** handle file system operations defensively:

- ✅ **DO**: Handle `FileNotFoundError` gracefully (race conditions are normal)
- ✅ **DO**: Catch `PermissionError` and log appropriately
- ✅ **DO**: Check for critical errors (disk full, read-only filesystem)
- ✅ **DO**: Use `pathlib.Path` for all file operations
- ✅ **DO**: Run blocking file operations in executor (`asyncio.to_thread`)
- ✅ **DO**: Implement retry logic for transient errors (EAGAIN, EBUSY, EINTR)
- ❌ **DON'T**: Assume files exist between glob and stat/unlink
- ❌ **DON'T**: Ignore OSError exceptions
- ❌ **DON'T**: Block the event loop with synchronous file operations
- ❌ **DON'T**: Retry critical errors (disk full, read-only filesystem)

**Race Conditions Are Expected:**
```python
# GOOD: Handle race conditions gracefully
try:
    p.unlink()
except FileNotFoundError:
    _LOGGER.debug("File already deleted (race condition): %s", p.name)
    deleted += 1  # Count as success - goal achieved
```

**Critical Errors Must Abort:**
```python
# GOOD: Stop immediately on disk full or read-only
except OSError as err:
    if err.errno == errno.ENOSPC:
        _LOGGER.error("Disk full - cannot complete cleanup")
        raise RuntimeError("Disk full") from err
    elif err.errno == errno.EROFS:
        _LOGGER.error("Read-only filesystem - cannot delete")
        raise RuntimeError("Filesystem is read-only") from err
```

### 3. Dry-Run Mode Compliance

**Dry-run mode MUST be respected everywhere:**

- ✅ **DO**: Check dry_run flag before ANY file deletion
- ✅ **DO**: Log dry-run actions at DEBUG level with `[DRY-RUN]` prefix
- ✅ **DO**: Count files that would be deleted in dry-run mode
- ✅ **DO**: Test all changes with dry-run mode enabled first
- ❌ **DON'T**: Skip dry-run checks for "cleanup" or "testing"
- ❌ **DON'T**: Delete files when dry_run is True under any circumstance

```python
# CORRECT pattern
if dry_run:
    _LOGGER.debug("[DRY-RUN] Would delete: %s", p.name)
    total_after += 1
    older_remaining += 1
    continue  # NEVER delete in dry-run mode
```

### 4. Safety Limits

**Max deletes limit prevents mass deletion accidents:**

- ✅ **DO**: Enforce max_deletes limit strictly
- ✅ **DO**: Log warning when limit is reached (once per run)
- ✅ **DO**: Count remaining old files when limit is hit
- ✅ **DO**: Use reasonable default (5000)
- ❌ **DON'T**: Bypass limit for "convenience"
- ❌ **DON'T**: Remove this safety mechanism

```python
# CORRECT implementation
if deleted >= max_deletes:
    if deleted == max_deletes:  # Log once
        _LOGGER.warning("Reached max deletion limit (%d)", max_deletes)
    total_after += 1
    older_remaining += 1
    continue  # Stop deleting
```

---

## Data Flow Contract (Scan vs Cleanup)

To avoid confusing UI states, scan and cleanup must remain strictly separated:

### Scan
- Updates file counts (e.g., total, older_than_retention)
- Updates `last_scan`
- MUST NOT change `deleted_last_run`

### Cleanup
- Performs deletion (unless dry-run)
- Updates counts after deletion
- Updates `deleted_last_run` (and bytes if available)
- Updates `last_cleanup`
- Always writes a run summary (even if 0 files deleted)

---

## Data Coordinator Pattern Compliance

**NEVER** bypass Home Assistant's data coordinator pattern:

- ✅ **DO**: Use `DataUpdateCoordinator` for periodic updates
- ✅ **DO**: Let entities pull data from coordinator's cache
- ✅ **DO**: Handle `UpdateFailed` exceptions properly
- ✅ **DO**: Run blocking operations with `asyncio.to_thread`
- ✅ **DO**: Update all entities atomically via coordinator
- ❌ **DON'T**: Make file operations directly from entity classes
- ❌ **DON'T**: Block the event loop with synchronous I/O
- ❌ **DON'T**: Update entities individually outside coordinator

**Correct Pattern:**
```python
# Coordinator method
async def _async_update_data(self) -> dict[str, Any]:
    result: ScanResult = await asyncio.to_thread(
        _scan_folder,
        self.base_path,
        self.pattern,
        self.retention_days,
    )
    return {"total_files": result.total_files, ...}

# Entity property
@property
def native_value(self) -> Any:
    return (self.coordinator.data or {}).get(self._key)
```

---

## Entity Creation and unique_id

**Trust Home Assistant's entity registry for deduplication:**

- ✅ **DO**: Assign stable `unique_id` based on entry_id + sensor type
- ✅ **DO**: Let `async_add_entities()` handle duplicate prevention
- ✅ **DO**: Include device name prefix in entity names
- ✅ **DO**: Use DeviceInfo to link entities to devices
- ❌ **DON'T**: Manually check for duplicate entities
- ❌ **DON'T**: Change `unique_id` format between versions
- ❌ **DON'T**: Base `unique_id` on user-configurable values

**unique_id format:**
```python
self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
# Example: "abc123_total_files"
```

**Entity naming with device prefix:**
```python
title = entry.title or coordinator.base_path
self._attr_name = f"{title} {sensor_name}"
# Example: "snapshots Total files"
```

This allows Home Assistant to display context-aware names (short in device view, full in lists).

---

## Logging Guidelines

**CRITICAL: Use appropriate log levels to avoid log spam:**

### ERROR (User must take action)
Use ERROR when the user needs to fix something:
- ❌ Permission denied on directory access
- ❌ Disk full or read-only filesystem
- ❌ Unexpected exceptions (bugs)

```python
_LOGGER.error("No permission to access directory %s: %s", base_path, str(e))
_LOGGER.error("Disk full - cannot complete cleanup operation")
```

### WARNING (Issues that will auto-retry or need attention)
Use WARNING for:
- ⚠️ Permission denied on individual files
- ⚠️ Max deletion limit reached
- ⚠️ Path not accessible
- ⚠️ Invalid configuration (caught by validation)

```python
_LOGGER.warning("No permission to delete file %s: %s", p.name, err)
_LOGGER.warning("Reached max deletion limit (%d) during cleanup", max_deletes)
```

### INFO (Normal important operations)
Use INFO for:
- ✅ Integration setup/unload
- ✅ Scheduled/manual cleanup runs (summary)
- ✅ Daily schedule setup

```python
_LOGGER.info("Setting up daily cleanup schedule for %s at %02d:%02d", path, h, m)
_LOGGER.info("Cleanup run (manual): deleted=%s dry_run=%s", deleted, dry_run)
```

### DEBUG (Detailed troubleshooting)
Use DEBUG for:
- 🔍 Individual file operations
- 🔍 Scan/cleanup progress
- 🔍 Dry-run actions
- 🔍 Race condition handling
- 🔍 Retry attempts

```python
_LOGGER.debug("Starting scan of %s with pattern '%s'", base_path, pattern)
_LOGGER.debug("Deleted file: %s (size: %d bytes)", p.name, file_size)
_LOGGER.debug("[DRY-RUN] Would delete: %s", p.name)
_LOGGER.debug("File disappeared during scan (race condition): %s", p.name)
```

**Log Level Decision Tree:**
```
Is this a problem?
├─ NO → Use INFO (success) or DEBUG (details)
└─ YES → Can the system recover automatically?
    ├─ YES → Use WARNING (will retry/continue)
    └─ NO → Does the user need to fix it?
        ├─ YES → Use ERROR (action required)
        └─ NO → Use ERROR with exc_info=True (bug)
```

---

## Git Commit Guidelines

**Commit message requirements:**

1. **Language**: ALL commit messages MUST be in English
2. **No AI attribution**: Do NOT include references to AI or Claude
3. **No co-author tags**: Do NOT add "Co-Authored-By: Claude"
4. **Format**: Use conventional commit format:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `refactor:` for code refactoring
   - `docs:` for documentation changes
   - `chore:` for maintenance tasks
5. **Style**: Write like a developer - short, concise, technical
   - Focus on WHAT changed, not elaborate explanations
   - Use present tense ("add" not "added")
   - Keep commit body concise (2-3 lines max if needed)
   - Same applies to PR descriptions and changelog entries
6. **Branch Policy**: Always check current branch - never commit directly to main/master
7. **Repository Info**: This repository uses `main` as the default branch (not `master`)

**HACS Default Repository PR Rule:**
- Never open `hacs/default` PRs from your repository `main/master`
- Always create a dedicated feature branch and open the PR from that branch

**Example commit messages:**

✅ **Good (concise, technical):**
```
fix: handle FileNotFoundError in cleanup loop

Count files as deleted if already removed (race condition).
```

✅ **Good:**
```
feat: add bytes tracking and performance metrics

- Add deleted_bytes_last_run sensor with DATA_SIZE device class
- Add scan/cleanup duration sensors in milliseconds
```

❌ **Bad (too verbose):**
```
feat: add performance tracking for scan and cleanup operations

This commit adds comprehensive performance tracking capabilities
to the integration. Duration sensors (in milliseconds) have been
added for both scan and cleanup operations to help users monitor
performance and identify issues. This will be useful for debugging
and optimization purposes.
```

❌ **Bad (AI attribution):**
```
Update file handling

🤖 Generated with Claude Code
Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

---

## Configuration Flow Validation

**Validate user inputs before accepting configuration:**

### Path Validation
- ✅ **DO**: Enforce `/media/` prefix for security
- ✅ **DO**: Strip trailing slashes for consistency
- ✅ **DO**: Show clear error messages
- ❌ **DON'T**: Allow paths outside `/media/`

```python
def _validate_base_path(value: str) -> str:
    value = (value or "").strip()
    if not value.startswith("/media/"):
        raise vol.Invalid("base_path_not_media")
    return value.rstrip("/")
```

### Pattern Validation
- ✅ **DO**: Block extremely dangerous patterns (`*`, `**/*`)
- ✅ **DO**: Check for invalid syntax (unclosed brackets, `***`)
- ✅ **DO**: Provide helpful error messages
- ❌ **DON'T**: Allow patterns that match ALL files

```python
def _validate_pattern(value: str) -> str:
    if value in ["*", "**/*"]:
        raise vol.Invalid("pattern_too_broad")
    if "***" in value:
        raise vol.Invalid("pattern_invalid_syntax")
    # ... more checks
    return value
```

### Time Validation
- ✅ **DO**: Validate HH:MM format with regex
- ✅ **DO**: Check hour (0-23) and minute (0-59) ranges
- ❌ **DON'T**: Accept invalid time values

---

## Scheduled Operations

**Daily cleanup scheduling:**

- ✅ **DO**: Use `async_track_time_change` for scheduling
- ✅ **DO**: Remove old listeners before setting new ones
- ✅ **DO**: Clean up listeners on unload
- ✅ **DO**: Log schedule setup and trigger events
- ❌ **DON'T**: Create duplicate schedules
- ❌ **DON'T**: Leave orphaned listeners

```python
async def async_setup_daily_schedule(self) -> None:
    self.async_remove_listeners()  # Remove old schedule first

    @callback
    async def _run_daily(now: datetime) -> None:
        await self.async_run_cleanup_now(triggered_by="schedule")

    self._unsub_daily = async_track_time_change(
        self.hass, _run_daily, hour=t.hour, minute=t.minute, second=0
    )
```

---

## Performance Optimization

**Optimize file operations for large directories:**

### Single stat() Call
- ✅ **DO**: Call `p.stat()` once and store result
- ✅ **DO**: Get both mtime and size from single stat
- ❌ **DON'T**: Call stat() multiple times per file

```python
# GOOD: Single stat() call
file_stat = p.stat()
mtime = file_stat.st_mtime
file_size = file_stat.st_size
```

### Retry Logic
- ✅ **DO**: Retry transient errors (EAGAIN, EBUSY, EINTR)
- ✅ **DO**: Use exponential backoff
- ✅ **DO**: Limit retry attempts (3 for scan, 2 for cleanup)
- ❌ **DON'T**: Retry critical errors (disk full, read-only)
- ❌ **DON'T**: Retry indefinitely

```python
async def _retry_async_operation(func, *args, max_retries: int = 3, delay: float = 0.5):
    for attempt in range(max_retries):
        try:
            return await func(*args)
        except OSError as e:
            if hasattr(e, 'errno') and e.errno in TRANSIENT_ERRORS:
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay * (2 ** attempt))
                    continue
            raise
```

---

## Sensor Configuration

### Performance Metrics
- `last_scan_duration_ms`: Scan duration in milliseconds
- `last_cleanup_duration_ms`: Cleanup duration in milliseconds
- Device class: `SensorDeviceClass.DURATION`
- State class: `SensorStateClass.MEASUREMENT`
- Category: `EntityCategory.DIAGNOSTIC`

### Data Size Tracking
- `deleted_bytes_last_run`: Total size of deleted files
- Device class: `SensorDeviceClass.DATA_SIZE`
- Unit: `UnitOfInformation.BYTES`
- State class: `SensorStateClass.MEASUREMENT`

### Timestamp Sensors
- `last_scan`: ISO timestamp of last scan
- `last_cleanup`: ISO timestamp of last cleanup
- Device class: `SensorDeviceClass.TIMESTAMP`
- Format: ISO 8601 (`2024-01-07T15:30:45`)
- Default: `None` (not `"-"`)

**Correct sensor definition:**
```python
SENSOR_DEFS = [
    ("deleted_bytes_last_run", "Deleted bytes last cleanup",
     UnitOfInformation.BYTES, "mdi:delete-circle-outline",
     None, SensorDeviceClass.DATA_SIZE, SensorStateClass.MEASUREMENT),

    ("last_scan", "Last scan", None, "mdi:folder-search",
     EntityCategory.DIAGNOSTIC, SensorDeviceClass.TIMESTAMP, None),
]
```

---

## HACS Release Requirements

**Before tagging a release, ALL of the following must be true:**

### Release Gates (must pass)
- ✅ HACS validation action passes with **no disabled/ignored checks**
- ✅ `manifest.json` keys are ordered: `domain`, `name`, then alphabetical
- ✅ No deprecated HA patterns (e.g. setting `self.config_entry = config_entry` in OptionsFlow)
- ✅ Release tag version matches `manifest.json` version
- ✅ If using CI/CD: `hassfest` passes with **no errors and no warnings** (Linux only)
- ✅ If `async_setup` exists, define: `CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)`

### Manifest Hygiene
- Do not add unnecessary manifest keys
- Avoid empty lists (e.g., `requirements: []`, `codeowners: []`)
- Keep the manifest minimal and HA-compliant

---

## Testing Requirements

**BEFORE committing changes:**

1. **Dry-run testing**: Test with dry_run enabled first
2. **Path validation**: Verify path restrictions work
3. **Pattern validation**: Test dangerous pattern blocking
4. **Race conditions**: Ensure FileNotFoundError is handled
5. **Error handling**: Test permission errors, disk full scenarios
6. **Limits**: Verify max_deletes limit works
7. **Performance**: Test with large directories (1000+ files)

**Required test scenarios:**
- Initial setup with valid configuration
- Path outside /media/ (should be rejected)
- Dangerous patterns: `*`, `**/*` (should be rejected)
- Dry-run mode (no files deleted)
- Max deletes limit reached
- Files deleted during operation (race condition)
- Permission denied on individual files
- Scheduled cleanup trigger
- Manual scan/cleanup buttons

---

## Backward Compatibility

**ALWAYS maintain compatibility with existing installations:**

- ✅ **DO**: Preserve existing config entry structure
- ✅ **DO**: Support existing entity unique IDs
- ✅ **DO**: Provide migration for config changes
- ✅ **DO**: Test upgrades from previous versions
- ❌ **DON'T**: Change entity unique IDs (breaks customizations)
- ❌ **DON'T**: Remove config options without migration
- ❌ **DON'T**: Break existing automations

### New Feature Implementation Rules

**All new features MUST:**
- Be **optional** with sensible defaults (backwards compatible)
- Be added to both **ConfigFlow** (initial setup) and **OptionsFlow** (reconfiguration)
- Have **translations** in strings.json for all UI elements
- Include **validation** in config_flow.py
- Update **coordinator** logic to handle the new option
- Consider **performance impact** on large folders (10k+ files)
- Be tested with **existing configs** to ensure no breaking changes

**Feature Interaction Guidelines:**
- New features should work **independently** (no forced dependencies)
- When features interact, clearly define **precedence rules**
- Example: `keep_minimum_files` takes precedence over `max_files_in_folder`
- Document interactions in code comments and CLAUDE.md

**Performance Considerations for File Operations:**
- **Cache** expensive calculations (folder size) between scans
- Use single **stat()** call per file, store results
- Consider **async/executor** pattern for heavy operations
- Add **progress logging** for operations on large folders
- Implement **early exit** conditions where possible

---

## When to Ask for Clarification

**ALWAYS** ask the user before:

1. Removing or weakening path validation
2. Changing file deletion logic
3. Modifying safety limits (dry-run, max_deletes)
4. Changing entity unique IDs or names
5. Removing existing sensors or features
6. Adding new file system operations
7. Implementing breaking changes to config structure

**NEVER** assume:

- It's safe to bypass safety checks for performance
- Dry-run mode can be ignored in "special cases"
- Path validation can be relaxed
- Files will always exist when you try to delete them
- User wants to increase default deletion limits

---

## Common Pitfalls to Avoid

### 1. File System Race Conditions
- ❌ Assuming files exist between glob and stat/unlink
- ✅ Always handle FileNotFoundError gracefully

### 2. Blocking the Event Loop
- ❌ Using synchronous file operations directly
- ✅ Always use `asyncio.to_thread` for blocking I/O

### 3. Ignoring Safety Mechanisms
- ❌ Bypassing dry-run checks
- ❌ Removing max_deletes limit
- ✅ Respect all safety features unconditionally

### 4. Poor Error Handling
- ❌ Ignoring OSError exceptions
- ❌ Not distinguishing transient from critical errors
- ✅ Handle each error type appropriately

---

## Summary for AI Assistants

**Core Principle: Safety Above All**

When working on this integration:

1. **NEVER** weaken file deletion safety mechanisms
2. **ALWAYS** respect dry-run mode unconditionally
3. **ALWAYS** enforce path restrictions (`/media/` only)
4. **ALWAYS** handle race conditions gracefully
5. **ALWAYS** use appropriate log levels
6. **ALWAYS** test with dry-run mode before production
7. **ALWAYS** ask for clarification when uncertain about safety

**This integration permanently deletes user files. Extreme caution is required for any changes to file operations, path validation, or safety mechanisms. When in doubt, ask the user for clarification rather than making assumptions.**

---

## Documentation Policy

**Where to document changes:**

- **CHANGELOG.md**: Version history, release notes, user-facing changes
- **Claude.md** (this file): Development guidelines, patterns, safety rules
- **README.md**: User documentation, installation, configuration

**DO NOT** add version-specific information to Claude.md. This file contains timeless development guidelines, not changelog entries.

### CHANGELOG.md Maintenance

**When to update:**
- Add changes to current version section as you work
- Only document integration changes (no README/docs-only updates)
- Keep entries short and technical (developer-style)

**Format:**
- Use Keep a Changelog categories: Added, Changed, Fixed, Removed
- No dates (available in GitHub Releases)
- Include compare links for all versions
- One line per change, focus on what changed

**Example:**
```markdown
## [1.0.6]

### Added
- `deleted_bytes_last_run` sensor with DATA_SIZE device class
- Pattern validation to block dangerous patterns

### Fixed
- Performance issue with double stat() calls
```
