# Retention Cleaner

Retention Cleaner is a Home Assistant custom integration that automatically
cleans up files in a configured folder based on a retention period.

Each device represents **one cleanup rule for one folder**.

---

## Features

- UI-based setup (Config Flow)
- One device = one folder cleanup rule
- Automatic daily cleanup at a configurable time
- Manual actions:
  - Scan now (count files only)
  - Run cleanup (delete files)
- Sensors:
  - Total files
  - Files older than retention
  - Deleted files in last cleanup
  - Last scan timestamp
  - Last cleanup timestamp
- Safety features:
  - Only paths under `/media/` are allowed
  - Optional dry-run mode (no deletion)
  - Configurable maximum deletes per run

---

## Important Safety Notes ⚠️

This integration **deletes files**.

Before enabling automatic cleanup:
- Verify the configured base path carefully
- Start with `dry_run = true`
- Use a reasonable `max_deletes` limit
- Test with the manual "Run cleanup" button

---

## Installation (HACS)

1. Open HACS → Integrations
2. Add custom repository:
   - Repository: `thomasgriebner/retention_cleaner`
   - Category: Integration
3. Install **Retention Cleaner**
4. Restart Home Assistant
5. Add the integration via:
   - Settings → Devices & Services → Add integration

---

## Configuration

All configuration is done via the Home Assistant UI.

Config options:
- Base path (must start with `/media/`)
- File pattern (glob, e.g. `**/*.jpg`)
- Retention days
- Daily cleanup time
- Dry-run mode
- Max deletes per cleanup run

---

## Typical Use Cases

- Camera snapshots and recordings
- Temporary exports or reports
- Automatically cleaning up automation artifacts
- Preventing uncontrolled storage growth

---

## Status

✅ Stable  
🧹 Actively maintained  
💥 Deletes files by design

---

## License

MIT License
