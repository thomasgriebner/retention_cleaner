# Bronze Tier Compliance TODO

## Status: 15/18 Bronze Rules Complete (83%)

Basierend auf Quality-Agent Analyse vom 2025-01-09.

---

## ❌ Kritische Lücken für Bronze Tier

### 1. **config-flow-test-coverage** (Aufwand: 4-6h)

**Problem:** Nur Validierungs-Unit-Tests vorhanden, keine echten HA Config Flow Integration Tests.

**Fehlende Tests:**
- Happy Path config flow completion
- Error handling in config flow UI
- Uniqueness validation (duplicate entries prevention)
- Config flow recovery from validation errors
- Options flow (reconfiguration) testing
- User-initiated flow testing

**Implementation Needed:**
```python
# tests/components/retention_cleaner/test_config_flow.py
# Test actual RetentionCleanerConfigFlow class with HA framework
# Mock HA config entries, test flow steps, error scenarios
```

### 2. **test-before-configure** (Aufwand: 2-3h)

**Problem:** Config flow validiert nur Syntax (Pfad-Format), nicht ob Pfad tatsächlich existiert/zugänglich ist.

**Fehlende Implementation in config_flow.py:**
```python
async def _test_path_access(self, base_path: str) -> None:
    """Test if path is accessible before configuring."""
    try:
        path = Path(base_path)
        if not await self.hass.async_add_executor_job(path.exists):
            raise vol.Invalid("path_does_not_exist")
        if not await self.hass.async_add_executor_job(path.is_dir):
            raise vol.Invalid("path_not_directory")
        # Test basic access
        await self.hass.async_add_executor_job(path.iterdir)
    except PermissionError:
        raise vol.Invalid("path_no_permission")
    except OSError:
        raise vol.Invalid("path_not_accessible")
```

**Error Messages in strings.json:**
```json
"error": {
    "path_does_not_exist": "The specified path does not exist",
    "path_not_directory": "The specified path is not a directory",
    "path_no_permission": "No permission to access the path",
    "path_not_accessible": "Path is not accessible"
}
```

### 3. **test-before-setup** (Aufwand: 1-2h)

**Problem:** `async_setup_entry` testet nicht ob konfigurierter Pfad zur Setup-Zeit noch zugänglich ist.

**Fehlende Implementation in __init__.py:**
```python
from homeassistant.exceptions import ConfigEntryNotReady

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    base_path = entry.data.get("base_path")

    # Test path accessibility before setup
    try:
        path = Path(base_path)
        if not await hass.async_add_executor_job(path.exists):
            raise ConfigEntryNotReady(f"Path does not exist: {base_path}")
        if not await hass.async_add_executor_job(path.is_dir):
            raise ConfigEntryNotReady(f"Path is not a directory: {base_path}")
    except PermissionError as err:
        raise ConfigEntryNotReady(f"No permission to access path: {base_path}") from err
    except OSError as err:
        raise ConfigEntryNotReady(f"Cannot access path: {base_path}") from err

    # Continue with existing setup...
```

---

## ⚠️ Architektur-Verbesserung

### **runtime-data Pattern** (Aufwand: 1-2h)

**Problem:** Verwenden veraltetes `hass.data[DOMAIN][entry.entry_id]` Pattern.

**Modern HA Pattern:**
```python
# In __init__.py
from dataclasses import dataclass

@dataclass
class RetentionCleanerData:
    coordinator: RetentionCleanerCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Replace hass.data usage with:
    entry.runtime_data = RetentionCleanerData(coordinator=coordinator)

# In all platform files (sensor.py, button.py, etc.)
async def async_setup_entry(...):
    coordinator = entry.runtime_data.coordinator  # Clean access
```

**Files to update:**
- `__init__.py` - Replace hass.data with entry.runtime_data
- `sensor.py` - Update coordinator access
- `button.py` - Update coordinator access
- `binary_sensor.py` - Update coordinator access

---

## ✅ Quick Wins Complete

- [x] **integration-owner**: Updated to "done" in quality_scale.yaml
- [x] **Current test coverage**: 21% mit 100% __init__.py coverage
- [x] **CI/CD Pipeline**: Läuft auf allen Branches

---

## 🎯 Prioritäten für nächste Session

1. **config-flow-test-coverage** (Höchste Priorität)
   - Größte Lücke für Bronze Tier
   - Erfordert echtes HA Testing Framework

2. **test-before-configure** (Sicherheit)
   - Wichtig für File-Delete Integration
   - Verbessert User Experience

3. **runtime-data** (Best Practice)
   - Moderne HA Architektur
   - Breaking Change - vorsichtig implementieren

4. **test-before-setup** (Robustheit)
   - Error handling verbessern
   - Setup-Failures eleganter behandeln

---

## 📚 Ressourcen

- [HA Integration Testing](https://developers.home-assistant.io/docs/development_testing)
- [Config Flow Testing](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/#testing)
- [Modern Integration Patterns](https://developers.home-assistant.io/docs/integration_setup/#storing-data)

---

## 💡 Hinweise

- **File-Delete Integration**: Extra Vorsicht bei allen Path-Validierungen
- **Backward Compatibility**: Runtime-data Change ist Breaking Change
- **Test Coverage**: Aktuell 21%, Bronze braucht nicht 100%
- **Error Messages**: Benutzerfreundliche Fehlermeldungen wichtig
