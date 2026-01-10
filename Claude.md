# Claude.md – Development Guidelines for Retention Cleaner

This document provides focused guidelines for AI assistants working on the Retention Cleaner Home Assistant integration. **Primary focus: Safe development to prevent accidental data loss.**

---

## PROJECT OVERVIEW

**Retention Cleaner** automatically deletes old files based on configurable retention rules. Manages camera recordings, snapshots, logs in `/media/` directory.

- **Tech**: Python 3.11+, asyncio, Home Assistant Core APIs
- **Type**: Local file operations with scheduled automation (HACS-compatible)
- **⚠️ CRITICAL**: This integration permanently deletes files from disk
- **Quality Target**: Type hints, tests, defensive programming

### Core Architecture
```
config_flow.py    → User configuration with validation
coordinator.py    → File scanning/deletion logic, scheduling
sensor.py         → File counts, timestamps, performance metrics
binary_sensor.py  → Path availability monitoring
button.py         → Manual scan/cleanup triggers
```

---

## CRITICAL SAFETY RULES

### 1. File Deletion Safety (MANDATORY)
- ✅ **ONLY** `/media/` paths allowed (enforced in config_flow)
- ✅ **RESPECT** dry-run mode unconditionally
- ✅ **ENFORCE** max_deletes safety limit strictly
- ✅ **VALIDATE** patterns (block `*`, `**/*`)
- ❌ **NEVER** bypass or weaken path validation
- ❌ **NEVER** ignore dry-run mode in any code path

### 2. Defensive Programming
```python
# ALWAYS use .get() for dynamic data
config.get("base_path", "/media/default")  # NOT config["base_path"]
data.get("total_files", 0)                # NOT data["total_files"]

# ALWAYS handle race conditions
try:
    p.unlink()
except FileNotFoundError:
    deleted += 1  # Count as success - goal achieved
```

### 3. Async/Threading Rules
- **ALL** filesystem I/O via executor: `await asyncio.to_thread(blocking_function, args)`
- **NEVER** use `time.sleep()` → use `await asyncio.sleep()`
- **ALWAYS** use `@callback` for event loop functions

### 4. Resource Cleanup
```python
# CRITICAL: Always clean up coordinators
async def test_something():
    coordinator = RetentionCleanerCoordinator(hass, entry)
    try:
        # test logic
    finally:
        await coordinator.async_shutdown()  # PREVENTS TIMER ERRORS
```

---

## ESSENTIAL DEVELOPMENT PATTERNS

### Data Flow Contract
**Scan**: Updates counts, `last_scan` timestamp. NEVER touches `deleted_last_run`
**Cleanup**: Performs deletion, updates `deleted_last_run`, `last_cleanup`. Always logs summary

### Modern Python (3.11+)
```python
# Pattern matching for errors
match error:
    case OSError(errno=errno.ENOSPC):
        raise UpdateFailed("Disk full")
    case OSError(errno=errno.EACCES):
        _LOGGER.warning("Permission denied: %s", path)

# Walrus operator
if (size := file_stat.st_size) > 0:
    total_bytes += size
```

### Entity Naming Best Practice
```python
# Include device name for multi-device disambiguation
self._attr_name = f"{device_name} {sensor_name}"
# Example: "Photos Cleanup Total files"
# HA shows context-appropriate names automatically
```

---

## TESTING STRATEGY

### Python Compatibility (3.11, 3.12+)
```python
# BAD: Fragile assertions
assert "Cleanup failed:" in str(exc_info.value)

# GOOD: Flexible exception checking
error_msg = str(exc_info.value).lower()
assert ("cleanup" in error_msg or "error" in error_msg)
```

### Resource Cleanup Patterns
```python
# ALWAYS use try/finally for coordinator tests
async def test_coordinator_feature():
    coordinator = RetentionCleanerCoordinator(hass, entry)
    try:
        await coordinator.async_refresh()  # NOT async_config_entry_first_refresh()
        # test logic
    finally:
        await coordinator.async_shutdown()
```

### Minimal Mocking
- **MOCK**: Filesystem operations (`pathlib.Path.*`), external APIs
- **DON'T MOCK**: Home Assistant core, DataUpdateCoordinator, your integration code

---

## COMPATIBILITY & RELEASE

### HACS Requirements
- ✅ `manifest.json` keys ordered: `domain`, `name`, then alphabetical
- ✅ Version in `manifest.json` matches git tag
- ✅ `hassfest` passes with no errors/warnings
- ✅ No deprecated HA patterns

### Release Gates (ALL must pass)
- ✅ HACS validation passes
- ✅ Tests pass on Python 3.11 AND 3.12+
- ✅ `hassfest` validation clean
- ✅ Version bumped in `manifest.json`

### Git Workflow
- **Main branch**: `main` (not `master`)
- **NEVER commit to main/master directly**
- **HACS PRs**: Always from feature branch, never from main
- **NO AI attribution**: Never mention Claude/AI in commits

---

## CORE COMMANDS

### Development
```bash
# Home Assistant dev mode
hass -c config

# Validation
python -m homeassistant.scripts.hassfest
hass --script check_config -c config

# Monitor logs
tail -f home-assistant.log | grep retention_cleaner
```

### Testing
```bash
# Tests run ONLY in GitHub Actions (not locally)
# Use CI/CD pipeline for all test validation
```

---

## CRITICAL REMINDERS

### File Operations
- **Race conditions are normal** - handle `FileNotFoundError` gracefully
- **Critical errors must abort** - disk full, read-only filesystem
- **Single stat() per file** - get mtime and size together

### Configuration
- **Path validation in config_flow:27-32** - never weaken
- **Pattern validation** - block dangerous patterns
- **Dry-run default** - always default to safe mode

### Logging Levels
- **ERROR**: User must fix (invalid config, critical errors)
- **WARNING**: Will auto-retry or degrade gracefully
- **INFO**: Important successful operations
- **DEBUG**: Detailed troubleshooting

---

## QUALITY CHECKLIST

### Before Implementation
- [ ] Read target function implementation
- [ ] Verify exact function names (never assume!)
- [ ] Plan minimal mocking strategy
- [ ] Consider Python 3.11/3.12 compatibility

### Before Release
- [ ] All tests pass on both Python versions
- [ ] HACS validation clean
- [ ] `hassfest` passes
- [ ] Safety mechanisms tested
- [ ] Dry-run mode verified

**Remember: This integration deletes files permanently. Safety comes before all other considerations.**
