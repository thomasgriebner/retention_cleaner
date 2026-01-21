# Retention Cleaner

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/thomasgriebner/retention_cleaner.svg)](https://github.com/thomasgriebner/retention_cleaner/releases)
[![License](https://img.shields.io/github/license/thomasgriebner/retention_cleaner.svg)](LICENSE)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/thomasgriebner/retention_cleaner/graphs/commit-activity)

Automatically clean up old files in Home Assistant based on configurable retention rules. Perfect for managing camera recordings, snapshots, and logs.

> **⚠️ Important:** This integration permanently deletes files. Always test with dry-run mode first and verify your configuration before enabling automated cleanup.

---

## Features

- **Rule-Based Cleanup** - Each device represents one folder with its own retention policy
- **Automated Scheduling** - Daily cleanup runs at your specified time
- **Safety First** - Dry-run mode, delete limits, and path restrictions protect against accidents
- **Performance Tracking** - Monitor scan/cleanup duration and deleted file sizes
- **Manual Control** - Test rules with scan/cleanup buttons before automation
- **Full UI Configuration** - No YAML editing required

---

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=thomasgriebner&repository=retention_cleaner&category=integration)

1. Click the badge above or open **HACS** → **Integrations**
2. Search for **Retention Cleaner**
3. Click **Download**
4. Restart Home Assistant

### Manual Installation

1. Copy `custom_components/retention_cleaner` to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

### Setup

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Retention Cleaner**
4. Configure your first cleanup rule
5. **Enable dry-run mode** to test safely

---

## Configuration

Each cleanup rule creates a device with the following configuration options:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| **Base Path** | string | - | Root directory to clean (must start with `/media/`) |
| **File Pattern** | string | `**/*.jpg` | Glob pattern for matching files |
| **Retention Days** | integer | `30` | Keep files newer than this many days (max: 3650 / 10 years) |
| **Cleanup Time** | time | `03:15` | Daily automatic cleanup schedule (HH:MM) |
| **Dry Run** | boolean | `false` | Test mode - count files without deleting |
| **Max Deletes** | integer | `5000` | Safety limit per cleanup run |
| **Only Extensions** | string | - | Keep only files with these extensions (e.g., `.mp4,.avi`) - case-insensitive |
| **Except Extensions** | string | - | Delete all files except these extensions (e.g., `.log,.tmp`) - case-insensitive |
| **Keep Minimum Files** | integer | `0` | Always preserve this many newest files (0-10,000), regardless of retention |
| **Max Files In Folder** | integer | `0` | Cap total number of files in folder (0-1,000,000), enforced after time-based cleanup (0 = disabled) |
| **Remove Empty Folders** | boolean | `false` | Remove empty subdirectories after file deletion (opt-in for safety) |

### Pattern Examples

| Use Case | Pattern | Description |
|----------|---------|-------------|
| Camera snapshots | `**/*.jpg` | All JPG files in subdirectories |
| Specific camera | `front_door/**/*.mp4` | Videos from front_door folder |
| Log files | `*.log` | Log files in root folder only |
| Multiple formats | `**/*.{jpg,png,mp4}` | Multiple file types |

### Extension Filtering

Control which file types are cleaned up:

| Use Case | Configuration | Description |
|----------|---------------|-------------|
| Only videos | `only_extensions: .mp4,.avi,.mkv` | Delete only video files |
| Keep videos | `except_extensions: .mp4,.avi` | Delete everything except videos |
| Default behavior | (leave empty) | Use File Pattern for matching |

**Rules:**
- Extensions are case-insensitive (`.MP4` matches `.mp4`)
- Use comma-separated list without spaces
- Cannot combine `only_extensions` and `except_extensions`
- Cannot use extension filters with custom File Pattern
- Extensions can start with or without a dot (`.mp4` or `mp4`)

### Minimum File Protection

Ensure you always keep recent files:

```yaml
Base Path: /media/backups
Retention Days: 7
Keep Minimum Files: 3
```

With this configuration:
- Files older than 7 days are candidates for deletion
- **But** the 3 newest files are always protected
- Useful for ensuring you have recent backups even if retention is aggressive

**Use Cases:**
- Backup safety: Always keep last N backups even with short retention
- Testing: Keep recent files while aggressively cleaning old ones
- Rolling logs: Maintain minimum recent logs regardless of age

**Valid Range:** 0-10,000 (0 = disabled)

### Maximum Files Limit

Cap the total number of files in a folder regardless of age:

```yaml
Base Path: /media/recordings
Retention Days: 30
Max Files In Folder: 100
```

With this configuration:
- First, files older than 30 days are deleted (time-based cleanup)
- Then, if more than 100 files remain, the oldest files are deleted until the count reaches 100
- Oldest files (by modification time) are removed first

**Order of Operations:**
1. Time-based cleanup runs first (retention_days)
2. File count enforcement runs second on remaining files

**Interactions:**
- Takes priority over `keep_minimum_files` (file count limit is enforced even if minimum would protect more files)
- Respects `max_deletes` safety limit (stops deletion when max_deletes is reached)
- Works with `dry_run` mode (shows what would be deleted)

**Use Cases:**
- Storage management: Keep folder size predictable (100 most recent files)
- Disk quotas: Prevent folder from exceeding file count limits
- Performance: Limit file count for faster directory scanning
- Backup rotation: Keep only N most recent backups

**Valid Range:** 0-1,000,000 (0 = disabled)

### Remove Empty Subdirectories After Cleanup

Automatically remove empty directory structures after cleaning up old files. This is particularly useful for camera systems that create date-based or event-based folder hierarchies.

```yaml
Base Path: /media/frigate/recordings
Pattern: **/*.mp4
Retention Days: 7
Remove Empty Folders: true
```

With this configuration:
- Files older than 7 days are deleted during cleanup
- After file deletion, empty parent directories are removed bottom-up
- Directories containing hidden files (e.g., `.gitkeep`, `.DS_Store`) are preserved
- The base_path itself is never removed

**How It Works:**
1. Standard file cleanup runs first (retention days, extension filters, file limits)
2. Parent directories of deleted files are identified
3. Directories are checked from deepest to shallowest (bottom-up traversal)
4. Empty directories are removed (no files and no subdirectories)
5. Process continues upward until non-empty directory or base_path is reached

**Order of Operations:**
1. Time-based cleanup (retention_days)
2. File count enforcement (max_files_in_folder)
3. Empty directory removal (remove_empty_folders) - runs last

**Interactions with Other Features:**
- **Dry-run mode:** When `dry_run: true`, directories are logged but not removed
- **All file cleanup features:** Runs after all file deletion operations complete
- **Scan operations:** Does not trigger during scan (only during cleanup)
- **Base path safety:** Never removes the configured `base_path` directory
- **Hidden files:** Directories containing files starting with `.` are preserved

**Use Cases:**
- Clean up empty date-based folders after removing old camera recordings (e.g., `/2024/01/15/`)
- Remove empty camera-specific subdirectories (e.g., `/cameras/front_door/snapshots/`)
- Maintain clean directory structures in multi-level storage hierarchies
- Reduce visual clutter in file browsers and media management systems

**Safety Features:**
- Opt-in by default (feature is disabled unless explicitly enabled)
- Hidden file preservation (intentional placeholder files like `.gitkeep` prevent removal)
- Base path protection (configured base_path is never removed)
- Dry-run support (test the feature safely before enabling actual deletion)
- Graceful error handling (permission errors are logged but don't stop cleanup)
- Race condition tolerance (handles concurrent file operations safely)

### Safety Guidelines

- Only `/media/` paths are allowed for security
- Symlinks are blocked at any level to prevent path traversal attacks
- Patterns like `*` or `**/*` are blocked to prevent accidents
- Always test with **dry-run mode** enabled first
- Use **Scan now** button to preview what will be deleted
- Start with a small **max deletes** limit for testing
- Verify paths are correct before disabling dry-run

---

## Entities

Each cleanup rule provides these entities:

### Sensors

| Entity | Description | Unit |
|--------|-------------|------|
| **Total files** | Current file count | files |
| **Older than retention** | Files eligible for deletion | files |
| **Deleted last cleanup** | Files deleted in last run | files |
| **Deleted bytes last cleanup** | Size of deleted files | bytes |
| **Last scan** | Timestamp of last scan | - |
| **Last cleanup** | Timestamp of last cleanup | - |
| **Last scan duration** | Performance metric | ms |
| **Last cleanup duration** | Performance metric | ms |

### Binary Sensor

| Entity | Description |
|--------|-------------|
| **Path available** | Monitors if the configured path is accessible |

### Buttons

| Entity | Description |
|--------|-------------|
| **Scan now** | Count files without deleting (safe preview) |
| **Run cleanup** | Execute cleanup immediately (respects dry-run setting) |

---

## Usage Examples

### Camera Recordings (Frigate)

Keep 7 days of snapshots, clean up nightly at 2 AM:

```yaml
Base Path: /media/frigate/snapshots
File Pattern: **/*.jpg
Retention Days: 7
Cleanup Time: 02:00
Dry Run: false
Max Deletes: 1000
```

### Per-Camera Cleanup

Separate retention rules for different cameras:

```yaml
# Front door - 14 days
Base Path: /media/frigate/recordings/front_door
File Pattern: *.mp4
Retention Days: 14

# Backyard - 7 days
Base Path: /media/frigate/recordings/backyard
File Pattern: *.mp4
Retention Days: 7
```

### Log File Management

Clean up old logs monthly:

```yaml
Base Path: /media/logs
File Pattern: *.log
Retention Days: 30
Cleanup Time: 04:00
Max Deletes: 100
```

### Selective Video Cleanup with Protection

Keep only video files, but always preserve the 5 newest:

```yaml
Base Path: /media/cameras/clips
Only Extensions: .mp4,.avi
Retention Days: 14
Keep Minimum Files: 5
Cleanup Time: 03:00
Max Deletes: 500
```

This setup:
- Only processes video files (.mp4, .avi)
- Deletes videos older than 14 days
- Always keeps the 5 newest videos (even if older than 14 days)
- Ignores all non-video files

### Camera Recordings with Empty Directory Cleanup

Keep 14 days of recordings and remove empty date folders:

```yaml
Base Path: /media/frigate/clips
Pattern: **/*.mp4
Retention Days: 14
Remove Empty Folders: true
Cleanup Time: 03:00
Max Deletes: 1000
```

This setup:
- Deletes MP4 files older than 14 days from date-based hierarchy (e.g., `/2024/01/15/camera/clip.mp4`)
- Removes empty directories after file deletion (e.g., empty `/2024/01/15/camera/` folder)
- Cleans up recursively until non-empty directory or base_path is reached
- Preserves directories containing hidden files like `.gitkeep`

---

## Advanced Configuration

### Debug Logging

To enable detailed logging, add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.retention_cleaner: debug
```

View logs in **Settings** → **System** → **Logs** or check `home-assistant.log`.

### Multiple Rules

Create multiple cleanup rules for different folders by adding the integration multiple times. Each rule runs independently with its own schedule.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Path not accessible | Verify path exists and starts with `/media/` |
| No files found | Check glob pattern matches your files |
| Files not deleting | Ensure dry-run is disabled |
| Permission denied | Check Home Assistant user has write permissions |
| Pattern validation error | Use more specific patterns (avoid `*` or `**/*`) |
| Extension filter not working | Ensure no File Pattern is set (use default `**/*.jpg` or leave empty) |
| Still has old files | Check if Keep Minimum Files is protecting them |
| Cannot set both extension filters | Use only `only_extensions` OR `except_extensions`, not both |

For more help, check the [issue tracker](https://github.com/thomasgriebner/retention_cleaner/issues).

---

## Requirements

- Home Assistant 2024.1.0 or newer
- HACS (recommended for installation)
- Write access to `/media/` directory

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Links

- [Report Issues](https://github.com/thomasgriebner/retention_cleaner/issues)
- [Home Assistant Community](https://community.home-assistant.io/)
- [HACS Documentation](https://hacs.xyz/)
