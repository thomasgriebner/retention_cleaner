# Claude.md – AI Development Guidelines for Retention Cleaner

This document provides comprehensive guidelines for Claude and other AI assistants working on the Retention Cleaner custom integration for Home Assistant. **The primary focus is on safe, cautious development to prevent accidental data loss and ensure system stability.**

---

## Project Overview

**Retention Cleaner** is a Home Assistant custom component that automatically deletes old files based on configurable retention rules. It manages camera recordings, snapshots, logs, and other files in the `/media/` directory.

- **Technology Stack**: Python 3.13+, asyncio, Home Assistant Core APIs
- **Integration Type**: Local file operations with scheduled automation (HACS-compatible)
- **Key Features**: Rule-based cleanup, dry-run mode, safety limits, performance tracking
- **⚠️ CRITICAL**: This integration permanently deletes files from disk
- **Quality Target**: Silver tier (type hints, tests, strict typing, guards against None)

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

## Modern Python Patterns

### Use Modern Language Features (Python 3.13+)

**Pattern Matching for Error Handling:**
```python
# GOOD: Clear error handling with pattern matching
match error:
    case OSError(errno=errno.ENOSPC):
        _LOGGER.error("Disk full - cannot complete cleanup")
        raise UpdateFailed("Disk full")
    case OSError(errno=errno.EACCES):
        _LOGGER.warning("Permission denied: %s", path)
    case OSError() as e if e.errno in TRANSIENT_ERRORS:
        # Retry transient errors
        await asyncio.sleep(0.5)
    case _:
        _LOGGER.error("Unexpected error", exc_info=True)
```

**Walrus Operator for Cleaner Code:**
```python
# GOOD: Avoid duplicate calls
if (size := file_stat.st_size) > 0:
    total_bytes += size
    
# GOOD: Inline validation
if not (path := config.get("base_path")):
    raise ValueError("base_path is required")
```

**Type Hints with Union Types:**
```python
# Python 3.10+ style
from typing import TypeAlias

ScanResult: TypeAlias = dict[str, int | float | str | None]

async def scan_folder(path: str) -> ScanResult | None:
    ...
```

### Async Best Practices

**Parallel Operations with asyncio.gather:**
```python
# GOOD: Parallel execution for better performance
scan_result, disk_info = await asyncio.gather(
    asyncio.to_thread(self._scan_folder),
    asyncio.to_thread(self._check_disk_space),
    return_exceptions=True,
)

# BAD: Sequential awaits
scan_result = await asyncio.to_thread(self._scan_folder)  # Slower
disk_info = await asyncio.to_thread(self._check_disk_space)
```

**Never Block the Event Loop:**
```python
# BAD: Blocks event loop
for p in Path(base_path).glob(pattern):  # ❌ Blocking I/O
    ...

# GOOD: Use executor for blocking operations
def _scan_sync(base_path: str, pattern: str) -> list[Path]:
    return list(Path(base_path).glob(pattern))

files = await asyncio.to_thread(_scan_sync, base_path, pattern)
```

### ConfigEntry Runtime Data Pattern

**Modern Pattern (HA 2024.3+):**
```python
# In __init__.py
from dataclasses import dataclass

@dataclass
class RetentionCleanerData:
    """Runtime data for retention cleaner."""
    coordinator: RetentionCleanerCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up retention cleaner from a config entry."""
    coordinator = RetentionCleanerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    # Store in runtime_data instead of hass.data
    entry.runtime_data = RetentionCleanerData(coordinator=coordinator)
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

# In sensors/buttons/etc
async def async_setup_entry(...):
    """Set up sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator  # Clean access
```

---

## Thread Safety Requirements

### Use @callback for Event Loop Functions

The `@callback` decorator marks functions that run in the Home Assistant event loop and must be thread-safe:

```python
from homeassistant.core import callback

# GOOD: Thread-safe state update
@callback
def _handle_coordinator_update(self) -> None:
    """Handle updated data from the coordinator."""
    # Only use thread-safe operations
    self.async_write_ha_state()

# GOOD: Schedule async task from callback
@callback
def _schedule_cleanup(self, now: datetime) -> None:
    """Schedule cleanup task - thread safe."""
    self.hass.async_create_task(
        self.async_run_cleanup_now(triggered_by="schedule")
    )
```

**Common Mistakes:**
```python
# ❌ BAD: Async function with @callback
@callback
async def _handle_update(self) -> None:  # Never async with @callback
    await self.async_refresh()

# ❌ BAD: Blocking I/O in callback
@callback
def _check_path(self) -> None:
    Path(self.base_path).exists()  # Blocking I/O!
```

### Thread-Safe Patterns

**State Updates:**
- Always use `async_write_ha_state()` for entity updates
- Never modify shared state without proper synchronization
- Use `self.hass.async_create_task()` to schedule async work

**Event Handlers:**
```python
# GOOD: Proper async task creation
@callback
def _handle_button_press(self) -> None:
    """Handle button press event."""
    self.hass.async_create_task(
        self._async_perform_cleanup()
    )

async def _async_perform_cleanup(self) -> None:
    """Perform the actual cleanup."""
    await self.coordinator.async_run_cleanup_now()
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
6. **Branch Policy**: 
   - Always check current branch before making changes
   - Never commit directly to main/master
   - If already on a feature branch, continue using it unless explicitly told to create a new branch
   - Only create new branches when starting completely new features or when explicitly requested
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

## Development Commands

### Running Home Assistant for Development

```bash
# Run Home Assistant in development mode
hass -c config

# Run with specific verbosity
hass -c config --log-level debug

# Check configuration validity
hass --script check_config -c config

# Validate manifest.json
python -m homeassistant.scripts.hassfest

# Monitor logs for this integration
tail -f home-assistant.log | grep retention_cleaner
```

### Testing in Dev Container

```bash
# Start dev container
devcontainer open .

# Run Home Assistant
hass -c /workspaces/test/config

# Run specific tests
pytest tests/components/retention_cleaner/ -xvs

# Test single file with coverage
pytest tests/components/retention_cleaner/test_sensor.py --cov=custom_components.retention_cleaner
```

### Quick Testing Workflow

1. **Copy to test environment:**
```bash
cp -r custom_components/retention_cleaner ~/.homeassistant/custom_components/
```

2. **Restart Home Assistant:**
```bash
ha core restart
# or in UI: Developer Tools → YAML → Restart
```

3. **Monitor logs:**
```bash
ha logs -f | grep retention_cleaner
```

4. **Test configuration:**
- Settings → Devices & Services → Add Integration
- Search for "Retention Cleaner"
- Test with `/media/test` path and safe pattern like `test*.txt`

---

## Code Quality Automation

### Pre-commit Setup

Create `.pre-commit-config.yaml` in the repository root:

```yaml
repos:
  # Format with Black
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3.13
        args: [--line-length=88]

  # Lint with Ruff (fast Python linter)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  # Type checking with mypy
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: 
          - homeassistant
          - types-python-dateutil
        args: [--strict, --ignore-missing-imports]

  # Security checks
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: [-r, custom_components/retention_cleaner/, -ll]
        exclude: tests/

  # Check YAML files
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-yaml
      - id: check-json
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-added-large-files
```

### Setup and Usage

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# Run on all files (first time setup)
pre-commit run --all-files

# Run on specific files
pre-commit run --files custom_components/retention_cleaner/*.py

# Update hook versions
pre-commit autoupdate

# Skip hooks temporarily (use sparingly!)
git commit --no-verify -m "Emergency fix"
```

### Ruff Configuration

Add to `pyproject.toml` or `ruff.toml`:

```toml
[tool.ruff]
target-version = "py313"
line-length = 88
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings  
    "F",   # pyflakes
    "I",   # isort
    "B",   # bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
    "ARG", # flake8-unused-arguments
    "SIM", # flake8-simplify
]
ignore = [
    "E501",  # Line too long (handled by black)
    "B008",  # Do not perform function calls in argument defaults
]

[tool.ruff.per-file-ignores]
"tests/*" = ["ARG"]  # Unused arguments are common in tests

[tool.ruff.isort]
force-sort-within-sections = true
known-first-party = ["custom_components.retention_cleaner"]
```

### Black Configuration

Add to `pyproject.toml`:

```toml
[tool.black]
line-length = 88
target-version = ["py313"]
include = '\.pyi?$'
extend-exclude = '''
/(
    \.git
  | \.mypy_cache
  | \.ruff_cache
  | build
  | dist
)/
'''
```

### MyPy Configuration

Add to `mypy.ini` or `pyproject.toml`:

```ini
[mypy]
python_version = 3.13
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_generics = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_unreachable = true
check_untyped_defs = true

[mypy-homeassistant.*]
ignore_missing_imports = true

[mypy-tests.*]
ignore_errors = true
```

### CI/CD Integration

For GitHub Actions, add `.github/workflows/quality.yml`:

```yaml
name: Code Quality

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          
      - name: Install dependencies
        run: |
          pip install -U pip
          pip install pre-commit
          
      - name: Run pre-commit
        run: pre-commit run --all-files
        
      - name: Run tests with coverage
        run: |
          pip install pytest pytest-cov
          pytest --cov=custom_components.retention_cleaner
```

### Quality Standards

**All code must pass:**
- ✅ Black formatting (automatic)
- ✅ Ruff linting with fixes applied
- ✅ MyPy strict type checking
- ✅ Bandit security checks
- ✅ Pre-commit hooks
- ✅ >80% test coverage

**Before merging PRs:**
- All quality checks pass
- No `# type: ignore` without justification
- No disabled linting rules without explanation
- All TODOs have associated issues

---

## Custom Error Types

Define specific error types for better error handling and debugging:

```python
# In const.py or errors.py
from homeassistant.exceptions import HomeAssistantError

class RetentionCleanerError(HomeAssistantError):
    """Base error for retention cleaner."""

class RetentionCleanerConfigError(RetentionCleanerError):
    """Configuration error requiring user action."""

class RetentionCleanerPermissionError(RetentionCleanerError):
    """Permission error on file operations."""

class RetentionCleanerDiskError(RetentionCleanerError):
    """Disk-related error (full, read-only)."""

# Usage in coordinator.py
try:
    p.unlink()
except OSError as err:
    if err.errno == errno.ENOSPC:
        raise RetentionCleanerDiskError("Disk full") from err
    elif err.errno == errno.EACCES:
        raise RetentionCleanerPermissionError(f"Cannot delete {p.name}") from err
```

---

## Testing Framework

### Pytest Setup and Configuration

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-homeassistant-custom-component pytest-cov

# Run all tests
pytest tests/components/retention_cleaner/ -xvs

# Run with coverage report
pytest tests/components/retention_cleaner/ --cov=custom_components.retention_cleaner --cov-report=term-missing

# Run specific test file
pytest tests/components/retention_cleaner/test_coordinator.py -xvs

# Run tests matching pattern
pytest -k "test_cleanup" -xvs
```

### Type Checking Requirements

```bash
# Install mypy
pip install mypy homeassistant-stubs

# Run strict type checking
mypy custom_components/retention_cleaner --strict

# Check specific file
mypy custom_components/retention_cleaner/coordinator.py --strict

# Ignore import errors for testing
mypy custom_components/retention_cleaner --strict --ignore-missing-imports
```

### Test Structure and Organization

```python
"""Test retention cleaner coordinator."""
from unittest.mock import AsyncMock, Mock, patch
import pytest
from freezegun import freeze_time

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.retention_cleaner.coordinator import RetentionCleanerCoordinator
from custom_components.retention_cleaner.const import DOMAIN

@pytest.fixture
async def coordinator(hass: HomeAssistant, config_entry: ConfigEntry):
    """Create a coordinator for testing."""
    coordinator = RetentionCleanerCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()
    return coordinator

@pytest.mark.asyncio
async def test_dry_run_mode_no_deletion(coordinator):
    """Test that dry-run mode doesn't delete files."""
    coordinator.dry_run = True
    
    with patch("pathlib.Path.glob") as mock_glob, \
         patch("pathlib.Path.unlink") as mock_unlink:
        
        # Setup mock files
        mock_files = [Mock(spec=Path) for _ in range(5)]
        mock_glob.return_value = mock_files
        
        result = await coordinator.async_run_cleanup_now()
        
        # No files should be deleted
        mock_unlink.assert_not_called()
        assert result["deleted_last_run"] == 0
```

### Required Test Coverage

**Minimum test scenarios that MUST be covered:**

1. **Safety Features:**
```python
async def test_path_restriction_enforced():
    """Test that paths outside /media/ are rejected."""
    with pytest.raises(ValueError, match="base_path_not_media"):
        validate_path("/home/user/important")

async def test_dangerous_pattern_rejected():
    """Test that dangerous patterns are blocked."""
    with pytest.raises(ValueError, match="pattern_too_broad"):
        validate_pattern("*")
```

2. **File Operations:**
```python
async def test_race_condition_handling(coordinator):
    """Test graceful handling of race conditions."""
    with patch("pathlib.Path.unlink") as mock_unlink:
        mock_unlink.side_effect = FileNotFoundError()
        
        result = await coordinator._cleanup_folder()
        
        # Should count as deleted (goal achieved)
        assert result["deleted_last_run"] > 0

async def test_permission_error_handling(coordinator):
    """Test handling of permission errors."""
    with patch("pathlib.Path.unlink") as mock_unlink:
        mock_unlink.side_effect = PermissionError()
        
        result = await coordinator._cleanup_folder()
        
        # Should log warning but continue
        assert "error" not in result
```

3. **Limits and Boundaries:**
```python
@pytest.mark.parametrize("max_deletes,files,expected", [
    (5, 10, 5),  # Limit reached
    (10, 5, 5),  # Less than limit
    (0, 10, 0),  # Zero limit
])
async def test_max_deletes_limit(coordinator, max_deletes, files, expected):
    """Test max_deletes limit enforcement."""
    coordinator.max_deletes = max_deletes
    # ... setup mock files
    result = await coordinator._cleanup_folder()
    assert result["deleted_last_run"] == expected
```

4. **Async Operations:**
```python
async def test_blocking_operations_in_executor(coordinator):
    """Test that blocking I/O uses executor."""
    with patch("asyncio.to_thread") as mock_to_thread:
        await coordinator._scan_folder()
        mock_to_thread.assert_called()
```

### Performance Testing

```python
@pytest.mark.performance
async def test_large_directory_performance(coordinator, tmp_path):
    """Test performance with large number of files."""
    import time
    
    # Create 10000 test files
    for i in range(10000):
        (tmp_path / f"file_{i}.txt").touch()
    
    coordinator.base_path = str(tmp_path)
    
    start = time.time()
    result = await coordinator._scan_folder()
    duration = time.time() - start
    
    assert duration < 5.0  # Should complete within 5 seconds
    assert result["total_files"] == 10000
```

### Integration Testing

```python
async def test_full_setup_flow(hass):
    """Test complete integration setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
        },
    )
    entry.add_to_hass(hass)
    
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    
    # Check coordinator is created
    assert entry.runtime_data.coordinator is not None
    
    # Check entities are created
    state = hass.states.get("sensor.test_total_files")
    assert state is not None
```

## Testing Requirements Checklist

**BEFORE committing changes:**

- [ ] Run full test suite with `pytest`
- [ ] Achieve >80% code coverage
- [ ] Pass strict type checking with `mypy`
- [ ] Test all safety features (dry-run, limits, validation)
- [ ] Test error handling (race conditions, permissions, disk errors)
- [ ] Test with large datasets (1000+ files)
- [ ] Test async operations don't block event loop
- [ ] Manual testing in real Home Assistant instance

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

## Common Anti-Patterns to Avoid

### 1. File System Race Conditions
- ❌ Assuming files exist between glob and stat/unlink
- ✅ Always handle FileNotFoundError gracefully

### 2. Blocking the Event Loop
```python
# ❌ BAD: Blocks event loop
for p in Path(path).glob("*"):
    p.stat()  # Blocking I/O in async context

# ✅ GOOD: Use executor
files = await asyncio.to_thread(
    lambda: list(Path(path).glob("*"))
)
```

### 3. Sequential Async Operations
```python
# ❌ BAD: Sequential awaits in loop
for path in paths:
    await self._scan_path(path)

# ✅ GOOD: Parallel with gather
results = await asyncio.gather(
    *[self._scan_path(p) for p in paths]
)
```

### 4. Ignoring Safety Mechanisms
- ❌ Bypassing dry-run checks
- ❌ Removing max_deletes limit
- ✅ Respect all safety features unconditionally

### 5. Poor Error Handling
- ❌ Ignoring OSError exceptions
- ❌ Not distinguishing transient from critical errors
- ✅ Handle each error type appropriately

### 6. Direct Dictionary Access
```python
# ❌ BAD: Can raise KeyError
value = config["some_key"]

# ✅ GOOD: Safe with default
value = config.get("some_key", default_value)
```

### 7. Hardcoded Paths
```python
# ❌ BAD: Platform-specific
path = "/media/folder\\file.txt"

# ✅ GOOD: Use pathlib
path = Path("/media") / "folder" / "file.txt"
```

### 8. Logging Sensitive Data
```python
# ❌ BAD: Never log passwords/tokens
_LOGGER.debug("Config: %s", config)  # May contain secrets

# ✅ GOOD: Log only safe data
_LOGGER.debug("Path: %s, Pattern: %s", path, pattern)
```

---

## Code Organization Best Practices

### File Structure
```
custom_components/retention_cleaner/
├── __init__.py          # Entry point, setup/unload
├── config_flow.py       # Configuration UI
├── coordinator.py       # Data update coordinator
├── const.py            # Constants and defaults
├── errors.py           # Custom exception types (if needed)
├── sensor.py           # Sensor entities
├── binary_sensor.py    # Binary sensor entities
├── button.py           # Button entities
├── strings.json        # Base translations
├── manifest.json       # Integration metadata
└── translations/       # Localized strings
    ├── en.json
    └── de.json
```

### Import Organization
```python
"""Module docstring."""
# Standard library
import asyncio
import errno
from datetime import datetime, timedelta
from pathlib import Path

# Third party
import voluptuous as vol

# Home Assistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform

# Local
from .const import DOMAIN, DEFAULT_RETENTION_DAYS
from .coordinator import RetentionCleanerCoordinator
```

### Docstring Standards
```python
def scan_folder(
    base_path: str,
    pattern: str,
    retention_days: int,
) -> dict[str, Any]:
    """Scan folder for files matching pattern.
    
    Args:
        base_path: Base directory to scan.
        pattern: Glob pattern for file matching.
        retention_days: Days to retain files.
        
    Returns:
        Dictionary with scan results including counts and timestamps.
        
    Raises:
        PermissionError: If directory cannot be accessed.
        ValueError: If path is invalid.
    """
```

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
