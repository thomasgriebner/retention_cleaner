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

### Pattern Examples

| Use Case | Pattern | Description |
|----------|---------|-------------|
| Camera snapshots | `**/*.jpg` | All JPG files in subdirectories |
| Specific camera | `front_door/**/*.mp4` | Videos from front_door folder |
| Log files | `*.log` | Log files in root folder only |
| Multiple formats | `**/*.{jpg,png,mp4}` | Multiple file types |

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
