# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.2.0] - 2026-02-03

### Added
- Configuration entities for runtime-editable configuration without restarting Home Assistant
  - **Number entities (4)**:
    - `retention_days` (1-3650 days) - Change retention period via UI, triggers immediate scan
    - `max_deletes` (1-10,000 files) - Maximum files to delete per cleanup run
    - `keep_minimum_files` (0-10,000 files) - Minimum files to always preserve
    - `max_files_in_folder` (0-1,000,000 files) - Maximum total files trigger cleanup
  - **Switch entities (2)**:
    - `dry_run` (on/off) - Toggle simulation mode without triggering scan (migrated from Select)
    - `remove_empty_folders` (on/off) - Auto-remove empty directories after cleanup
  - **Text entities (3)**:
    - `pattern` - Edit glob pattern (e.g., `**/*.jpg`) with validation against dangerous patterns
    - `only_extensions` - Comma-separated include list for file extensions (e.g., `.mp4,.jpg`)
    - `except_extensions` - Comma-separated exclude list for file extensions (e.g., `.tmp,.log`)
    - All text entities validate input (extension format, pattern safety) and enforce mutual exclusion rules
  - **Time entity (1)**:
    - `run_at` (HH:MM format) - Change daily cleanup time, automatically reschedules next cleanup
  - **Sensor (1)**:
    - `base_path` (read-only, diagnostic category) - Displays configured base path
  - All config entities use `EntityCategory.CONFIG` for proper UI grouping (except base_path sensor which uses DIAGNOSTIC)
- ConfigSnapshot pattern for race-condition prevention during cleanup operations
  - Immutable config snapshots captured at start of scan/cleanup operations
  - Configuration changes during operations don't affect in-progress scans/cleanups
  - Changes take effect on next operation for consistency
- Live configuration updates trigger immediate coordinator refresh
  - Number, Text, and Time entity changes trigger automatic scan to update file counts
  - Switch entity changes update config only (no scan needed)
  - Changes are atomic and immediately persisted via `async_update_config_value()`
- Cross-field validation for pattern and extension mutual exclusion
  - Prevents simultaneous use of custom pattern with extension filters
  - Enforces only_extensions OR except_extensions, not both
  - Validation enforced at both config flow and entity update time

### Changed
- Migrated `dry_run` from Select entity (Off/On options) to Switch entity (on/off) for better user experience
- Sensor entities no longer expose configuration as attributes (`base_path`, `pattern`, `retention_days` removed from sensor attributes)
- Configuration now managed through dedicated config entities for frequently changed values
- Options flow remains for initial setup, but runtime changes use config entities
- Sensor units: `suggested_unit_of_measurement=MEGABYTES` with `precision=2` for deleted_bytes sensors
- Test coverage improved to 99.17% with 416 comprehensive tests including new entity platforms
- All entity platforms now properly integrated (number, switch, text, time, sensor platforms)

### Breaking Changes
- **Removed sensor attributes**: `base_path`, `pattern`, and `retention_days` no longer available as sensor extra_state_attributes
  - Migration: Use the new config entities instead (automatically created for all instances)
  - `base_path` is now a separate diagnostic sensor entity (read-only)
  - `pattern` is now an editable text entity (triggers scan on change)
  - `retention_days` is now an editable number entity (triggers scan on change)
  - Existing automations or templates reading sensor attributes must be updated to use new entity IDs

## [1.1.1] - 2026-01-26

### Fixed
- Config flow validation error when configuring extension filters with default pattern value. Users can now set Only Extensions or Except Extensions without manually clearing the pattern field.

## [1.1.0]

### Added
- Support for `/share/` directory alongside `/media/` as allowed base path
  - Same security validation (symlink blocking, path traversal prevention) applies to both paths
  - UI strings and error messages updated to mention both allowed paths
  - German translations updated to reflect both allowed paths
- Extension filtering for selective cleanup (closes #15)
  - `only_extensions` option: Delete only specified file extensions (e.g., `.mp4,.jpg`)
  - `except_extensions` option: Delete all files except specified extensions (e.g., `.mkv,.log`)
  - Case-insensitive extension matching
  - Mutual exclusion validation: Use either file pattern OR extension filters
  - User-friendly comma-separated syntax for extensions
- Minimum file protection for retention safety
  - `keep_minimum_files` option: Always preserve N newest files (0-10,000)
  - Protects recent backups even with aggressive retention policies
  - Works seamlessly with all other filters (retention days, size, extensions, pattern)
  - Default: 0 (feature disabled)
- Maximum files limit per folder (closes #18)
  - `max_files_in_folder` option: Cap total number of files in directory (0-1,000,000)
  - Enforces file count limit after time-based cleanup
  - Deletes oldest files (by modification time) to reach target
  - Takes priority over `keep_minimum_files` setting
  - Respects `max_deletes` safety limit and `dry_run` mode
  - Default: 0 (feature disabled)
- Empty directory removal after cleanup
  - `remove_empty_folders` option: Remove empty subdirectories after file deletion
  - Runs bottom-up after all file cleanup operations complete
  - Preserves directories containing hidden files (e.g., `.gitkeep`, `.DS_Store`)
  - Never removes the configured `base_path` directory
  - Respects `dry_run` mode for safe testing
  - Gracefully handles race conditions and permission errors
  - Default: false (opt-in for safety)
- Folder size monitoring sensors for storage tracking
  - `total_folder_size_bytes` sensor: Shows total size of all files matching pattern/extension filters
  - `older_than_retention_size_bytes` sensor: Shows size of files eligible for deletion
  - Both sensors use DATA_SIZE device class for automatic unit conversion (KB/MB/GB)
  - Zero performance impact: Size calculated during existing file scan
  - Updates on every scan operation
  - Useful for comparing storage usage across multiple cleanup rules

### Changed
- Improved code quality with refactored helpers and reduced duplication
- Performance optimization: Cached extension set parsing

### Fixed
- Runtime safety checks to prevent misconfiguration with empty filters

## [1.0.10]

### Added
- State restoration support: Sensor values now persist across Home Assistant restarts
  - File count sensors retain their values (total files, older than retention, deleted last run)
  - Timestamp sensors maintain last scan and cleanup times
  - Performance metrics preserved (scan/cleanup duration)
  - Binary sensor state persists (path availability)

### Changed
- Test coverage improved to 90%+ with comprehensive state restoration testing
- All tests verified on Python 3.11 and 3.12

## [1.0.9]

### Fixed
- Use datetime objects with UTC timezone for TIMESTAMP device class sensors

## [1.0.8]

### Fixed
- (Reserved for already released version)

## [1.0.7]

### Fixed
- Remove invalid `configuration_url` from DeviceInfo (local paths not allowed)

## [1.0.6]

### Added
- Device name prefix to entity names for context-aware display
- `deleted_bytes_last_run` sensor with DATA_SIZE device class
- `last_scan_duration_ms` and `last_cleanup_duration_ms` performance sensors
- Pattern validation to block dangerous patterns (`*`, `**/*`)
- German translations for all new features

### Changed
- Icons updated to modern outline variants
- Type hints improved across all entity classes
- TIMESTAMP device class for `last_scan` and `last_cleanup` sensors

### Fixed
- Performance issue with double stat() calls (now single call per file)

## [1.0.5]

### Added
- Comprehensive debug logging throughout codebase
- Retry logic for transient file system errors (EAGAIN, EBUSY, EINTR)
- Specific exception types (disk full, read-only, permission errors)
- Docstrings for all coordinator methods

### Changed
- Improved error handling with automatic retries and exponential backoff

## [1.0.4]

### Added
- Distinctive icons for sensor entities
- Integration icons for Home Assistant UI

## [1.0.3]

### Fixed
- Hassfest manifest and config schema warnings

## [1.0.2]

### Changed
- Simplified entity names (device provides context)

## [1.0.1]

### Added
- Device registration for folder rules
- `last_scan` and `last_cleanup` timestamp sensors

## [1.0.0]

### Added
- Initial HACS release
- Rule-based file cleanup with retention policies
- Dry-run mode for safe testing
- Manual scan and cleanup buttons
- Binary sensor for path availability
- Daily scheduled cleanup
- Safety limits (max deletes, /media/ path restriction)
- Config flow for UI configuration
- Glob pattern support

[1.2.0]: https://github.com/thomasgriebner/retention_cleaner/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/thomasgriebner/retention_cleaner/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/thomasgriebner/retention_cleaner/compare/v1.0.10...v1.1.0
[1.0.10]: https://github.com/thomasgriebner/retention_cleaner/compare/v1.0.9...v1.0.10
[1.0.9]: https://github.com/thomasgriebner/retention_cleaner/compare/v1.0.8...v1.0.9
[1.0.8]: https://github.com/thomasgriebner/retention_cleaner/compare/v1.0.7...v1.0.8
[1.0.7]: https://github.com/thomasgriebner/retention_cleaner/compare/v1.0.6...v1.0.7
[1.0.6]: https://github.com/thomasgriebner/retention_cleaner/compare/v1.0.5...v1.0.6
[1.0.5]: https://github.com/thomasgriebner/retention_cleaner/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/thomasgriebner/retention_cleaner/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/thomasgriebner/retention_cleaner/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/thomasgriebner/retention_cleaner/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/thomasgriebner/retention_cleaner/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/thomasgriebner/retention_cleaner/releases/tag/v1.0.0
