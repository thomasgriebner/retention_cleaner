# Retention Cleaner (Home Assistant)

Retention Cleaner is a custom Home Assistant integration that automatically
cleans up files in a configured folder based on a retention period.

Each configured device represents **one cleanup rule for one folder**.

## Key Features

- UI-based setup (Config Flow)
- One device = one folder / rule
- Automatic daily cleanup
- Manual "Run now" button
- Sensors for:
  - total files
  - files older than retention
  - deleted files in last run
  - last cleanup timestamp
- Safe by default:
  - only paths under `/media/` allowed
  - optional dry-run mode
  - configurable max deletes per run

## Status

🚧 **Early development / MVP**

The integration is under active development.
APIs, entities, and configuration options may still change.

## Installation (planned)

This integration will be installable via **HACS** as a custom repository.

Instructions will be added once the first stable release is available.

## License

MIT License
