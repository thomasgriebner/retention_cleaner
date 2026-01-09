# Silver Tier Quality Plan for Retention Cleaner

## Goal
Achieve Home Assistant Silver Tier quality standards while remaining a HACS integration.

## Current Status
- ✅ Already in home-assistant/brands repository
- ✅ Most Silver requirements already met
- ❌ Missing: Test coverage
- ❌ Missing: quality_scale.yaml

## Silver Tier Requirements Checklist

### ✅ Already Complete
- [x] Config Flow UI implementation
- [x] Entity unique IDs
- [x] Error recovery and handling
- [x] Automatic offline recovery
- [x] Detailed documentation
- [x] Troubleshooting possible
- [x] Config entry unloading
- [x] Entity unavailable states
- [x] Logging when unavailable
- [x] Brands repository entry

### ❌ TODO: Test Implementation

#### Phase 1: Config Flow Tests
```python
# tests/test_config_flow.py
- Test valid configuration
- Test path validation (/media/ restriction)
- Test pattern validation (block dangerous patterns)
- Test time format validation (HH:MM)
- Test duplicate entry prevention
- Test options flow
```

#### Phase 2: Coordinator Tests
```python
# tests/test_coordinator.py
- Test scan_folder with mock files
- Test cleanup_folder with dry-run mode
- Test cleanup_folder with actual deletion
- Test error handling:
  - Permission denied
  - Disk full
  - File not found (race condition)
  - Invalid path
- Test schedule setup
- Test data update
```

#### Phase 3: Entity Tests
```python
# tests/test_sensor.py
- Test sensor value updates
- Test sensor availability
- Test restored state

# tests/test_button.py
- Test button press actions
- Test button availability

# tests/test_binary_sensor.py
- Test path availability detection
```

### ❌ TODO: Quality Scale File

Create `quality_scale.yaml`:
```yaml
rules:
  # Bronze Tier
  appropriate-library: done
  brands: done  # We're in the brands repo
  common-modules: done
  config-flow: done
  config-flow-test-coverage: todo
  dependency-transparency: done
  docs-actions: done
  docs-high-level-description: done
  docs-installation-instructions: done
  docs-removal-instructions: done
  entity-event-setup: done
  entity-name-setup: done
  entity-unique-id: done
  has-entity: done
  runtime-data: done
  
  # Silver Tier
  action-exceptions: done
  config-entry-unloading: done
  docs-configuration-parameters: done
  docs-installation-parameters: done
  entity-unavailable: done
  integration-owner: exempt  # Solo maintainer
  log-when-unavailable: done
  parallel-updates: done
  reauthentication-flow: exempt  # Not applicable for local files
  test-before-configure: todo
  test-before-setup: todo
  unique-config-entry: done
```

## Test Infrastructure Setup

### 1. Create Test Structure
```
tests/
├── __init__.py
├── conftest.py          # pytest fixtures
├── test_config_flow.py
├── test_coordinator.py
├── test_sensor.py
├── test_button.py
└── test_binary_sensor.py
```

### 2. GitHub Actions Workflow
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install pytest pytest-cov pytest-asyncio
      - run: pip install homeassistant
      - run: pytest tests/ --cov=custom_components/retention_cleaner
```

### 3. Key Test Fixtures
```python
# tests/conftest.py
import pytest
from unittest.mock import patch, MagicMock
from homeassistant.core import HomeAssistant

@pytest.fixture
def mock_hass():
    """Return a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    # Setup required hass properties
    return hass

@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    # Mock config entry with test data
    pass

@pytest.fixture
def mock_file_system():
    """Mock file system operations."""
    with patch('pathlib.Path.glob') as mock_glob:
        # Setup mock files
        yield mock_glob
```

## Documentation Improvements

### Extend README.md with:
- Troubleshooting section
- Common error messages and solutions
- More configuration examples
- FAQ section

### Example Troubleshooting Section:
```markdown
## Troubleshooting

### "Permission Denied" errors
- Ensure Home Assistant has read/write access to the media folder
- Check folder permissions: `ls -la /media/`

### Files not being deleted
- Check if dry_run mode is enabled
- Verify the file pattern matches your files
- Check the retention_days setting
- Review logs for specific errors

### Sensors showing "Unknown" after restart
- This is normal, sensors update after first scan
- Wait for scheduled scan or trigger manual scan
```

