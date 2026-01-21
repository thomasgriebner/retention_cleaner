# Claude.md – Development Guidelines for Retention Cleaner

This document provides high-level guidelines for AI assistants working on the Retention Cleaner Home Assistant integration. **Primary focus: Safe development to prevent accidental data loss.**

---

## PROJECT OVERVIEW

**Retention Cleaner** automatically deletes old files based on configurable retention rules. Manages camera recordings, snapshots, logs in `/media/` directory.

- **Tech**: Python 3.11+, asyncio, Home Assistant Core APIs
- **Type**: Local file operations with scheduled automation (HACS-compatible)
- **⚠️ CRITICAL**: This integration permanently deletes files from disk
- **Quality Target**: 100% test coverage, type hints, defensive programming

### Core Architecture
```
config_flow.py    → User configuration with validation
coordinator.py    → File scanning/deletion logic, scheduling
sensor.py         → File counts, timestamps, performance metrics
binary_sensor.py  → Path availability monitoring
button.py         → Manual scan/cleanup triggers
```

---

## SPECIALIZED AGENTS

This project uses **4 specialized agents** for different development tasks. **Always delegate work to the appropriate agent instead of doing it yourself.**

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| **ha-feature-coordinator** | Orchestrate feature lifecycle | • New features (plans, coordinates, reviews)<br>• Complex refactoring<br>• Multi-agent coordination needed |
| **ha-integration-developer** | Implement production code | • Code changes in `custom_components/`<br>• Update `manifest.json` version<br>• Safety-critical implementation |
| **ha-integration-test-writer** | Write and fix tests | • Tests in `tests/` directory<br>• Fix failing tests<br>• Improve test coverage |
| **ha-documentation-writer** | Update documentation | • Update `README.md`<br>• Update `CHANGELOG.md`<br>• Document new features |

### When to Use Each Agent

**For new features or complex changes:**
→ Use `ha-feature-coordinator` agent
- Manages full TDD workflow (Test → Implement → Review)
- Coordinates between developer and test agents
- Ensures quality before code is written
- Handles versioning and documentation

**For simple bug fixes or small changes:**
→ Use agents directly as needed
- `ha-integration-developer` for code fixes
- `ha-integration-test-writer` for test fixes
- `ha-documentation-writer` for doc updates

**Troubleshooting Agent Spawning:**
If the coordinator reports Task tool unavailability or API concurrency errors:
- This is a temporary API issue, not a configuration problem
- **Workaround:** Spawn sub-agents directly (developer, test-writer, doc-writer)
- The coordinator can still provide guidance and quality oversight
- See agent files for detailed spawning instructions

**See agent files in `.claude/agents/` for detailed guidelines:**
- `ha-feature-coordinator.md` - Complete TDD workflow, versioning, quality gates
- `ha-integration-developer.md` - Code patterns, safety rules, self-review checklist
- `ha-integration-test-writer.md` - Testing patterns, test standards, fixtures
- `ha-documentation-writer.md` - README/CHANGELOG update guidelines

---

## CRITICAL SAFETY RULES

### ⚠️ File Deletion Safety (LIFE-CRITICAL)

This integration **permanently deletes files from disk**. These rules are **MANDATORY**:

1. **Path Validation**
   - ✅ ONLY `/media/` paths allowed (enforced in `config_flow.py:27-32`)
   - ❌ NEVER weaken path validation

2. **Dry-Run Mode**
   - ✅ ALWAYS respect dry-run mode
   - ❌ NEVER bypass dry-run in any code path

3. **Max Deletes Limit**
   - ✅ ALWAYS enforce max_deletes safety limit
   - ❌ NEVER bypass the limit

4. **Pattern Validation**
   - ✅ Block dangerous patterns (`*`, `**/*`)
   - ❌ NEVER allow unvalidated patterns

5. **Defensive Programming**
   ```python
   # ALWAYS use .get() for dict access (race conditions)
   config.get("base_path", "/media/default")  # NOT config["base_path"]

   # ALWAYS handle FileNotFoundError (files can disappear)
   try:
       file_path.unlink()
   except FileNotFoundError:
       deleted += 1  # Goal achieved - file is gone
   ```

6. **Resource Cleanup**
   ```python
   # ALWAYS clean up coordinators in tests
   coordinator = RetentionCleanerCoordinator(hass, entry)
   try:
       # test logic
   finally:
       await coordinator.async_shutdown()  # PREVENTS TIMER ERRORS
   ```

---

## DEVELOPMENT ENVIRONMENT

### Project Setup
- **Path**: `~/repos/retention_cleaner`
- **Python 3.11**: `source venv/bin/activate`
- **Python 3.12**: `source venv312/bin/activate`
- **Tests**: Must pass on BOTH Python versions

### Running Tests
```bash
# Python 3.11
source venv/bin/activate && pytest tests/ -v

# Python 3.12
source venv312/bin/activate && pytest tests/ -v
```

### Validation Commands
```bash
# HACS validation
python -m homeassistant.scripts.hassfest

# Config check
hass --script check_config -c config

# Monitor logs
tail -f home-assistant.log | grep retention_cleaner
```

---

## GIT WORKFLOW

- **Main branch**: `main` (protected, use PRs)
- **Feature branches**: Create from `main`, name descriptively
- **Commits**: Semantic style (`feat:`, `fix:`, `docs:`, `test:`)
- **NO AI attribution**: Write commits like a developer would
- **NEVER commit to main directly**: Always use pull requests

---

## RELEASE REQUIREMENTS

All must pass before release:
- ✅ Tests pass on Python 3.11 AND 3.12
- ✅ 100% test coverage maintained
- ✅ `hassfest` validation clean
- ✅ HACS validation passes
- ✅ Version in `manifest.json` updated
- ✅ `CHANGELOG.md` updated
- ✅ Safety mechanisms tested

---

## KEY DATA FLOW

**Scan Operation** (read-only):
- Updates: `total_files`, `older_than_retention`, `last_scan`
- NEVER touches: `deleted_last_run`

**Cleanup Operation** (destructive):
- Updates: `deleted_last_run`, `deleted_bytes_last_run`, `last_cleanup`
- Respects: dry-run mode, max_deletes limit, pattern validation

---

## REMEMBER

**This integration deletes files permanently. Safety comes before all other considerations.**

When in doubt:
1. Use the appropriate specialized agent (`.claude/agents/*.md`)
2. Read existing code before making changes
3. Add validation, error handling, and tests
4. Default to safe mode (dry-run=True)
5. Test on BOTH Python versions

**Detailed guidelines are in the specialized agent files - refer to them for implementation details.**
