# Retention Cleaner for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/thomasgriebner/retention_cleaner.svg)](https://github.com/thomasgriebner/retention_cleaner/releases)
[![License](https://img.shields.io/github/license/thomasgriebner/retention_cleaner.svg)](LICENSE)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/thomasgriebner/retention_cleaner/graphs/commit-activity)

A Home Assistant custom integration that automatically manages file retention by cleaning up old files based on configurable rules. Perfect for managing camera recordings, snapshots, logs, and temporary files.

## ⚠️ Important Safety Notice

**This integration permanently deletes files.** Always test with dry-run mode first and ensure your paths are correctly configured.

## ✨ Features

### Core Functionality

* **🎯 Rule-Based Cleanup**: Each device represents one folder cleanup rule
* **⏰ Automated Scheduling**: Daily cleanup at your specified time
* **🔍 File Scanning**: Monitor file counts before deletion
* **🎛️ Full UI Configuration**: No YAML editing required
* **🚦 Smart Error Handling**: Distinguishes between critical and recoverable errors

### Safety Features

* **🔒 Path Restriction**: Only `/media/` paths allowed for safety
* **🧪 Dry-Run Mode**: Test your rules without deleting files
* **🎚️ Delete Limits**: Configure maximum files to delete per run
* **✅ Manual Controls**: Test with manual scan/cleanup before automation
* **🔄 Retry Logic**: Automatic retry for transient errors
* **⚡ Race Condition Handling**: Gracefully handles files deleted during operations
* **📝 Comprehensive Logging**: Debug, info, warning, and error levels for full visibility

### Home Assistant Entities

Each cleanup rule creates a device with:

| Entity Type | Description |
|------------|-------------|
| \*\*Sensors\*\* | • Total files count<br>• Files older than retention<br>• Deleted files (last run)<br>• Last scan timestamp<br>• Last cleanup timestamp |
| \*\*Binary Sensor\*\* | Path availability status |
| \*\*Buttons\*\* | • Scan now (count only)<br>• Run cleanup (delete files) |

## 📋 Requirements

* Home Assistant 2024.1.0 or newer
* HACS (for easy installation)
* Access to `/media/` directory in Home Assistant
* Appropriate file permissions for deletion operations

## 🚀 Installation

### Via HACS (Recommended)

1. **Add Custom Repository**

   * Open HACS → Integrations
   * Click menu (3 dots top right) → Custom repositories
   * Add repository: `https://github.com/thomasgriebner/retention_cleaner`
   * Category: Integration
   * Click Add

2. **Install Integration**

   * Search for "Retention Cleaner"
   * Click Install
   * Restart Home Assistant

3. **Configure**

   * Go to Settings → Devices & Services
   * Click "+ Add Integration"
   * Search for "Retention Cleaner"
   * Follow the configuration wizard

### Manual Installation

1. Copy `custom_components/retention_cleaner` to your Home Assistant's `custom_components` directory
2. Restart Home Assistant
3. Follow configuration steps above

## 🛡️ Advanced Safety & Reliability

### Error Handling
The integration includes sophisticated error handling:
- **Automatic Retry**: Transient errors (busy resources, temporary locks) trigger automatic retries with exponential backoff
- **Specific Error Detection**: Distinguishes between permission errors, disk full, read-only filesystem, and race conditions
- **Graceful Degradation**: Individual file errors don't stop the entire cleanup process
- **Critical Error Protection**: Disk full and read-only filesystem errors immediately abort operations

### Logging Levels
The integration provides detailed logging at multiple levels for troubleshooting:

#### Enable Debug Logging
Add to your `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.retention_cleaner: debug
```

#### Log Levels Explained
- **DEBUG**: Detailed file operations, scan progress, individual deletions
- **INFO**: Scheduled runs, cleanup summaries, configuration changes
- **WARNING**: Permission issues, file access problems, limit reached
- **ERROR**: Critical failures, disk full, read-only filesystem

#### View Logs
After enabling debug logging and restarting Home Assistant:
1. Go to **Settings** → **System** → **Logs**
2. Or check the log file: `home-assistant.log`
3. Filter for "retention_cleaner" to see relevant entries

## ⚙️ Configuration

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| \*\*Base Path\*\* | string | - | Root directory to clean (must start with `/media/`) |
| \*\*File Pattern\*\* | string | `\*\*/\*` | Glob pattern for files to match |
| \*\*Retention Days\*\* | integer | `7` | Keep files newer than this |
| \*\*Cleanup Time\*\* | time | `03:15` | Daily cleanup schedule (HH:MM) |
| \*\*Dry Run\*\* | boolean | `true` | Test mode - count but don't delete |
| \*\*Max Deletes\*\* | integer | `5000` | Maximum files to delete per run |

### Configuration Examples

#### Camera Snapshots

```yaml
Base Path: /media/frigate/snapshots
File Pattern: \*\*/\*.jpg
Retention Days: 7
Cleanup Time: 02:00
Dry Run: false
Max Deletes: 1000
```

#### Log Files

```yaml
Base Path: /media/logs
File Pattern: \*.log
Retention Days: 30
Cleanup Time: 04:00
Dry Run: false
Max Deletes: 100
```

#### Recording Cleanup by Camera

```yaml
Base Path: /media/frigate/recordings/front_door
File Pattern: \*.mp4
Retention Days: 14
Cleanup Time: 03:00
Dry Run: false
Max Deletes: 500
```

## 🔧 Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| \*\*Path not accessible\*\* | Ensure path exists and starts with `/media/` |
| \*\*No files found\*\* | Check your glob pattern matches files |
| \*\*Files not being deleted\*\* | Verify dry_run is set to false |
| \*\*Too many files deleted\*\* | Reduce max_deletes value |
| \*\*Permission denied\*\* | Check file/folder permissions for Home Assistant user |
| \*\*Disk full errors\*\* | Free up disk space before running cleanup |
| \*\*Files disappearing\*\* | Normal behavior - handles race conditions automatically |

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

* Home Assistant Community for the amazing platform
* HACS for simplified distribution
* All contributors and users providing feedback

## 🔗 Links

* [Report Issues](https://github.com/thomasgriebner/retention_cleaner/issues)
* [Home Assistant Community](https://community.home-assistant.io/)
* [HACS Documentation](https://hacs.xyz/)

---

**Remember**: This integration deletes files permanently. Always backup important data and test thoroughly before production use.

