# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.1.0]

### Added
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

### Changed
- Test coverage maintained at 100% (170 tests across Python 3.11 and 3.12)
- Improved code quality with refactored helpers and reduced duplication
- Enhanced test suite with parametrized tests and helper fixtures (19.9% reduction in test code)
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
