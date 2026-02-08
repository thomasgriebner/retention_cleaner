# Retention Cleaner

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/thomasgriebner/retention_cleaner.svg)](https://github.com/thomasgriebner/retention_cleaner/releases)
[![License](https://img.shields.io/github/license/thomasgriebner/retention_cleaner.svg)](LICENSE)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/thomasgriebner/retention_cleaner/graphs/commit-activity)

Automatically clean up old files in Home Assistant based on retention rules. Perfect for managing camera recordings, snapshots, and backups without SSH or cron jobs.

> **⚠️ Important:** This integration permanently deletes files. Always test with dry-run mode first.

## Features

- Configurable retention policies per folder
- Runtime configuration via UI entities (no restart needed)
- Daily automated cleanup scheduling
- Dry-run mode for safe testing
- Extension filtering (include/exclude specific file types)
- Minimum file protection and maximum file limits
- Automatic empty directory cleanup
- Storage monitoring sensors
- Manual scan and cleanup buttons
- Path safety restrictions (`/media/` and `/share/` only)

---

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=thomasgriebner&repository=retention_cleaner&category=integration)

1. Open **HACS** → **Integrations**
2. Search for **Retention Cleaner**
3. Click **Download**
4. Restart Home Assistant

### Manual Installation

1. Copy `custom_components/retention_cleaner` to your `custom_components` directory
2. Restart Home Assistant

### Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **Retention Cleaner**
3. Configure your first cleanup rule (path, pattern, retention)
4. **Enable dry-run mode** and test with "Scan now" button
5. Verify the files to be deleted, then disable dry-run mode

---

## Quick Start

Clean up Frigate camera recordings older than 7 days:

```yaml
Base Path: /media/frigate/recordings
File Pattern: **/*.mp4
Retention Days: 7
Cleanup Time: 03:00
Dry Run: ON  # Test first!
```

After configuring, click **"Scan now"** to preview what will be deleted. Check the `older_than_retention` sensor. If correct, disable dry-run mode.

---

## Configuration

Each cleanup rule is configured during setup and can be adjusted at runtime via UI entities (v1.2.0+).

| Parameter | Type | Default | Editable | Description |
|-----------|------|---------|----------|-------------|
| **Base Path** | string | - | No | Root directory to clean (must start with `/media/` or `/share/`) |
| **File Pattern** | string | `**/*.jpg` | Yes | Glob pattern for matching files (e.g., `**/*.mp4`) |
| **Retention Days** | integer | `30` | Yes | Delete files older than X days (1-3650) |
| **Cleanup Time** | time | `03:15` | Yes | Daily automatic cleanup schedule (HH:MM) |
| **Dry Run** | boolean | `false` | Yes | Test mode - preview deletions without actually deleting |
| **Max Deletes** | integer | `5000` | Yes | Safety limit per cleanup run (1-10,000) |
| **Only Extensions** | string | - | Yes | Include only these extensions (e.g., `.mp4,.avi`) |
| **Except Extensions** | string | - | Yes | Exclude these extensions (e.g., `.log,.tmp`) |
| **Keep Minimum Files** | integer | `0` | Yes | Always preserve X newest files (0-10,000) |
| **Max Files In Folder** | integer | `0` | Yes | Cap total files, delete oldest (0-1,000,000, 0 = disabled) |
| **Remove Empty Folders** | boolean | `false` | Yes | Remove empty subdirectories after cleanup |

### Runtime Configuration (v1.2.0+)

All configuration parameters (except base path) can be changed at runtime via UI entities without restarting Home Assistant. Changes to retention days, pattern, or extensions trigger an automatic scan to update file counts.

**Automate configuration changes** in response to disk space or schedules:

```yaml
automation:
  - alias: "Reduce retention when disk space low"
    trigger:
      - platform: numeric_state
        entity_id: sensor.disk_use_percent
        above: 85
    action:
      - service: number.set_value
        target:
          entity_id: number.front_camera_retention_days
        data:
          value: 7
```

### Pattern Examples

| Use Case | Pattern |
|----------|---------|
| Camera snapshots | `**/*.jpg` |
| Specific camera | `front_door/**/*.mp4` |
| Log files | `*.log` |
| Multiple formats | `**/*.{jpg,png,mp4}` |

### Advanced Features

**Extension Filtering:**
- `only_extensions: .mp4,.avi` - Delete only specified types
- `except_extensions: .log,.tmp` - Delete everything except specified types
- Case-insensitive, cannot combine both options

**Minimum File Protection:**
- `keep_minimum_files: 5` - Always preserve X newest files regardless of age
- Useful for ensuring you always have recent backups

**Maximum Files Limit:**
- `max_files_in_folder: 1000` - Cap total files, delete oldest when exceeded
- Runs after time-based cleanup, respects safety limits

**Storage Monitoring:**
- `total_folder_size_bytes` - Total size of all matched files
- `older_than_retention_size_bytes` - Size of files to be deleted
- Updates automatically during scans, displayed as GB/MB/KB

**Empty Directory Cleanup:**
- `remove_empty_folders: true` - Remove empty subdirectories after cleanup
- Preserves directories with hidden files (`.gitkeep`)
- Never removes the base path itself

### Safety Features

- Only `/media/` and `/share/` paths allowed
- Symlinks blocked to prevent path traversal
- Dangerous patterns (`*`, `**/*`) rejected
- Dry-run mode for safe testing
- Configurable delete limits (1-10,000 per run)

---

## Entities

Each cleanup rule creates a device with the following entities:

**Configuration (v1.2.0+):**
- Number: `retention_days`, `max_deletes`, `keep_minimum_files`, `max_files_in_folder`
- Switch: `dry_run`, `remove_empty_folders`
- Text: `pattern`, `only_extensions`, `except_extensions`
- Time: `run_at` (daily cleanup schedule)
- Sensor: `base_path` (read-only)

**Sensors:**
- `total_files` - Current file count
- `older_than_retention` - Files eligible for deletion
- `deleted_last_cleanup` - Files deleted in last run
- `deleted_bytes_last_cleanup` - Size of deleted files
- `total_folder_size_bytes` - Total size of matched files
- `older_than_retention_size_bytes` - Size of files to be deleted
- `last_scan`, `last_cleanup` - Timestamps (diagnostic)
- `last_scan_duration`, `last_cleanup_duration` - Performance metrics (diagnostic)

**Binary Sensor:**
- `path_available` - Monitors if path is accessible

**Buttons:**
- `scan_now` - Preview deletions without removing files
- `run_cleanup` - Execute cleanup immediately

---

## Examples

### Camera Recordings

```yaml
Base Path: /media/frigate/recordings
Pattern: **/*.mp4
Retention Days: 7
Cleanup Time: 03:00
```

### Backups with Minimum Protection

```yaml
Base Path: /share/backups
Pattern: *.tar.gz
Retention Days: 14
Keep Minimum Files: 3  # Always keep 3 newest
```

### Video Files Only

```yaml
Base Path: /media/cameras
Only Extensions: .mp4,.avi
Retention Days: 30
Max Files In Folder: 1000  # Cap at 1000 files
```

### Multiple Cameras

Create separate rules for different retention periods:

```yaml
# Front door - 14 days
Base Path: /media/frigate/recordings/front_door
Pattern: **/*.mp4
Retention Days: 14

# Backyard - 7 days
Base Path: /media/frigate/recordings/backyard
Pattern: **/*.mp4
Retention Days: 7
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Path not accessible | Verify path exists and starts with `/media/` or `/share/` |
| No files found | Check glob pattern matches your files |
| Files not deleting | Ensure dry-run is disabled |
| Permission denied | Check Home Assistant has write permissions |
| Pattern validation error | Use specific patterns (avoid `*` or `**/*`) |
| Extension filter not working | Cannot combine with custom pattern |
| Cannot set both extension filters | Use `only_extensions` OR `except_extensions`, not both |
| Config changes not taking effect | Changes trigger automatic scan, check sensors |

**Enable debug logging** in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.retention_cleaner: debug
```

---

## Requirements

- Home Assistant 2024.1.0 or newer
- Write access to `/media/` or `/share/` directory

---

## Support

- [Report Issues](https://github.com/thomasgriebner/retention_cleaner/issues)
- [Home Assistant Community](https://community.home-assistant.io/)
- [CHANGELOG](CHANGELOG.md)

---

## License

MIT License - see [LICENSE](LICENSE) file for details.
