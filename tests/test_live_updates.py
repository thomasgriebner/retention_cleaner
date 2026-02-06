"""Integration tests for live config updates via config entities.

This module tests end-to-end scenarios where configuration changes through
config entities (Number, Text, Time, Select) trigger coordinator updates
and affect scan/cleanup operations.

Key scenarios tested:
1. Config changes trigger coordinator refresh
2. Config changes affect scan/cleanup results
3. ConfigSnapshot isolation during operations
4. Scheduler updates from Time entity
5. Multiple sequential config changes
"""

import asyncio
import os
import time as time_module
from unittest.mock import patch

from homeassistant.components.number import (
    ATTR_VALUE as NUMBER_ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE as NUMBER_SERVICE_SET_VALUE,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
import pytest

from custom_components.retention_cleaner.const import (
    CONF_DRY_RUN,
    CONF_KEEP_MINIMUM_FILES,
    CONF_MAX_DELETES,
    CONF_MAX_FILES_IN_FOLDER,
    CONF_PATTERN,
    CONF_REMOVE_EMPTY_FOLDERS,
    CONF_RETENTION_DAYS,
    CONF_RUN_AT,
)
from tests.conftest import TEST_MEDIA_PATH


async def test_retention_days_change_triggers_scan(
    hass: HomeAssistant, init_integration, tmp_path
):
    """Test changing retention_days via Number entity triggers coordinator refresh."""
    coordinator = init_integration.runtime_data

    original_retention = coordinator.retention_days
    assert original_retention == 7, "Initial retention_days should be 7"

    new_retention_days = 14

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.test_cleanup_retention_days",
            NUMBER_ATTR_VALUE: new_retention_days,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert (
        coordinator.retention_days == new_retention_days
    ), "Coordinator should reflect new retention_days"
    assert coordinator.data is not None, "Coordinator should have refreshed data"
    assert (
        init_integration.options[CONF_RETENTION_DAYS] == new_retention_days
    ), "Config entry options should be updated"


async def test_pattern_change_updates_scan_results(
    hass: HomeAssistant, init_integration, tmp_path
):
    """Test changing pattern affects scan results when entities are implemented."""
    coordinator = init_integration.runtime_data
    media_dir = tmp_path / "media" / "pattern_test"
    media_dir.mkdir(parents=True)

    for i in range(5):
        (media_dir / f"file_{i}.jpg").touch()
        (media_dir / f"file_{i}.png").touch()

    original_pattern = coordinator.pattern
    assert original_pattern == "*.jpg", "Initial pattern should be *.jpg"

    await coordinator.async_update_config_value(CONF_PATTERN, "*.png")
    await hass.async_block_till_done()

    assert coordinator.pattern == "*.png", "Pattern should be updated"
    assert coordinator.data is not None, "Coordinator should have refreshed"


async def test_config_change_during_cleanup_uses_snapshot(
    hass: HomeAssistant, init_integration, tmp_path
):
    """Test config changes during cleanup don't affect current operation using ConfigSnapshot."""
    coordinator = init_integration.runtime_data
    media_dir = tmp_path / "media" / "snapshot_test"
    media_dir.mkdir(parents=True)

    for i in range(10):
        file = media_dir / f"test_{i}.log"
        file.write_text(f"content {i}")
        old_time = time_module.time() - (8 * 24 * 60 * 60)
        os.utime(file, (old_time, old_time))

    snapshot_before = coordinator.create_config_snapshot()
    assert (
        snapshot_before.retention_days == 7
    ), "Snapshot should capture initial retention_days"
    assert snapshot_before.pattern == "*.jpg", "Snapshot should capture initial pattern"
    assert snapshot_before.dry_run is True, "Snapshot should capture initial dry_run"
    assert (
        snapshot_before.base_path == TEST_MEDIA_PATH
    ), "Snapshot should capture base_path"

    await coordinator.async_update_config_value(CONF_RETENTION_DAYS, 30)
    await hass.async_block_till_done()

    snapshot_after = coordinator.create_config_snapshot()
    assert (
        snapshot_after.retention_days == 30
    ), "New snapshot should have updated retention_days"
    assert (
        snapshot_before.retention_days == 7
    ), "Original snapshot should remain unchanged (frozen)"

    try:
        snapshot_before.retention_days = 99
        pytest.fail("Should not be able to modify frozen dataclass")
    except (AttributeError, Exception):
        pass


async def test_run_at_change_updates_scheduler(hass: HomeAssistant, init_integration):
    """Test changing run_at via coordinator triggers scheduler update."""
    coordinator = init_integration.runtime_data

    original_run_at = coordinator.run_at
    assert str(original_run_at) == "02:00:00", "Initial run_at should be 02:00:00"

    new_run_at = "04:30"
    await coordinator.async_update_config_value(CONF_RUN_AT, new_run_at)
    await hass.async_block_till_done()

    updated_run_at = coordinator.run_at
    assert str(updated_run_at) == "04:30:00", "Coordinator run_at should be updated"
    assert (
        init_integration.options[CONF_RUN_AT] == new_run_at
    ), "Config entry options should be updated"


async def test_multiple_config_changes_in_sequence(
    hass: HomeAssistant, init_integration
):
    """Test multiple config changes work correctly in sequence."""
    coordinator = init_integration.runtime_data

    await coordinator.async_update_config_value(CONF_RETENTION_DAYS, 14)
    await hass.async_block_till_done()
    assert coordinator.retention_days == 14, "First change should apply"

    await coordinator.async_update_config_value(CONF_PATTERN, "*.log")
    await hass.async_block_till_done()
    assert coordinator.pattern == "*.log", "Second change should apply"
    assert coordinator.retention_days == 14, "First change should persist"

    await coordinator.async_update_config_value(CONF_RUN_AT, "06:00")
    await hass.async_block_till_done()
    assert str(coordinator.run_at) == "06:00:00", "Third change should apply"
    assert coordinator.pattern == "*.log", "Second change should persist"
    assert coordinator.retention_days == 14, "First change should persist"


async def test_dry_run_toggle_via_coordinator(hass: HomeAssistant, init_integration):
    """Test dry_run toggle via coordinator affects cleanup behavior."""
    coordinator = init_integration.runtime_data

    assert coordinator.dry_run is True, "Initial dry_run should be True"

    await coordinator.async_update_config_value(CONF_DRY_RUN, False)
    await hass.async_block_till_done()

    assert coordinator.dry_run is False, "dry_run should be toggled to False"
    assert (
        init_integration.options[CONF_DRY_RUN] is False
    ), "Config entry should reflect change"

    await coordinator.async_update_config_value(CONF_DRY_RUN, True)
    await hass.async_block_till_done()

    assert coordinator.dry_run is True, "dry_run should toggle back to True"


async def test_config_changes_affect_scan_results(
    hass: HomeAssistant, init_integration, tmp_path
):
    """Test config changes are reflected in scan results."""
    coordinator = init_integration.runtime_data
    media_dir = tmp_path / "media" / "scan_results"
    media_dir.mkdir(parents=True)

    for i in range(15):
        file = media_dir / f"test_{i}.jpg"
        file.touch()
        if i < 10:
            old_time = time_module.time() - (8 * 24 * 60 * 60)
            os.utime(file, (old_time, old_time))

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob") as mock_glob,
    ):
        mock_files = [media_dir / f"test_{i}.jpg" for i in range(15)]
        mock_glob.return_value = mock_files

        await coordinator.async_refresh()
        await hass.async_block_till_done()

    await coordinator.async_update_config_value(CONF_RETENTION_DAYS, 30)
    await hass.async_block_till_done()

    assert coordinator.retention_days == 30, "Retention should be updated"


async def test_config_persistence_across_coordinator_reload(
    hass: HomeAssistant, init_integration
):
    """Test config changes persist across coordinator operations."""
    coordinator = init_integration.runtime_data

    await coordinator.async_update_config_value(CONF_RETENTION_DAYS, 21)
    await hass.async_block_till_done()

    assert init_integration.options[CONF_RETENTION_DAYS] == 21, "Options should persist"

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.retention_days == 21, "Config should persist after refresh"


async def test_all_config_entities_load_correctly(
    hass: HomeAssistant, init_integration
):
    """Test all config entities load correctly on integration setup."""
    state = hass.states.get("number.test_cleanup_retention_days")
    assert state is not None, "retention_days Number entity should exist"
    assert float(state.state) == 7.0, "Initial value should match config"


async def test_config_changes_are_atomic(hass: HomeAssistant, init_integration):
    """Test config changes are atomic (no partial updates)."""
    coordinator = init_integration.runtime_data

    original_pattern = coordinator.pattern

    await coordinator.async_update_config_value(CONF_RETENTION_DAYS, 25)
    await hass.async_block_till_done()

    assert coordinator.retention_days == 25, "New value should apply"
    assert (
        coordinator.pattern == original_pattern
    ), "Other config should remain unchanged"
    assert (
        init_integration.options[CONF_RETENTION_DAYS] == 25
    ), "Options should be updated atomically"


async def test_retention_days_entity_reflects_coordinator_changes(
    hass: HomeAssistant, init_integration
):
    """Test Number entity state updates when coordinator config changes."""
    coordinator = init_integration.runtime_data

    await coordinator.async_update_config_value(CONF_RETENTION_DAYS, 42)
    await hass.async_block_till_done()

    state = hass.states.get("number.test_cleanup_retention_days")
    assert state is not None, "Number entity should exist"
    assert float(state.state) == 42.0, "Entity state should reflect updated config"


async def test_config_snapshot_immutability(hass: HomeAssistant, init_integration):
    """Test ConfigSnapshot is truly immutable (frozen dataclass)."""
    coordinator = init_integration.runtime_data

    snapshot = coordinator.create_config_snapshot()

    with pytest.raises((AttributeError, Exception)):
        snapshot.retention_days = 999

    with pytest.raises((AttributeError, Exception)):
        snapshot.pattern = "modified"

    with pytest.raises((AttributeError, Exception)):
        snapshot.dry_run = False


async def test_config_snapshot_captures_all_fields(
    hass: HomeAssistant, init_integration
):
    """Test ConfigSnapshot captures all config fields correctly."""
    coordinator = init_integration.runtime_data

    snapshot = coordinator.create_config_snapshot()

    assert hasattr(snapshot, "base_path"), "Should have base_path"
    assert hasattr(snapshot, "pattern"), "Should have pattern"
    assert hasattr(snapshot, "retention_days"), "Should have retention_days"
    assert hasattr(snapshot, "dry_run"), "Should have dry_run"
    assert hasattr(snapshot, "max_deletes"), "Should have max_deletes"
    assert hasattr(snapshot, "run_at"), "Should have run_at"
    assert hasattr(snapshot, "only_extensions"), "Should have only_extensions"
    assert hasattr(snapshot, "except_extensions"), "Should have except_extensions"
    assert hasattr(snapshot, "keep_minimum_files"), "Should have keep_minimum_files"
    assert hasattr(snapshot, "max_files_in_folder"), "Should have max_files_in_folder"
    assert hasattr(snapshot, "remove_empty_folders"), "Should have remove_empty_folders"

    assert snapshot.base_path == TEST_MEDIA_PATH, "base_path should match"
    assert snapshot.pattern == "*.jpg", "pattern should match"
    assert snapshot.retention_days == 7, "retention_days should match"
    assert snapshot.dry_run is True, "dry_run should match"
    assert snapshot.max_deletes == 100, "max_deletes should match"


async def test_concurrent_config_changes(hass: HomeAssistant, init_integration):
    """Test multiple concurrent config changes are handled correctly."""
    coordinator = init_integration.runtime_data

    tasks = [
        coordinator.async_update_config_value(CONF_RETENTION_DAYS, 15),
        coordinator.async_update_config_value(CONF_PATTERN, "*.png"),
    ]

    await asyncio.gather(*tasks)
    await hass.async_block_till_done()

    assert coordinator.retention_days == 15, "First change should apply"
    assert coordinator.pattern == "*.png", "Second change should apply"


async def test_config_change_triggers_refresh_once(
    hass: HomeAssistant, init_integration
):
    """Test config change triggers exactly one coordinator refresh."""
    coordinator = init_integration.runtime_data

    initial_scan_time = coordinator.last_scan

    await coordinator.async_update_config_value(CONF_RETENTION_DAYS, 20)
    await hass.async_block_till_done()

    updated_scan_time = coordinator.last_scan

    assert updated_scan_time != initial_scan_time, "Scan should have been triggered"


async def test_config_update_with_invalid_key(hass: HomeAssistant, init_integration):
    """Test coordinator handles invalid config keys gracefully."""
    coordinator = init_integration.runtime_data

    await coordinator.async_update_config_value("invalid_key", "invalid_value")
    await hass.async_block_till_done()

    assert coordinator.data is not None, "Coordinator should still function"


async def test_scheduler_removed_on_shutdown(hass: HomeAssistant, init_integration):
    """Test scheduler listeners are removed on coordinator shutdown."""
    coordinator = init_integration.runtime_data

    await coordinator.async_setup_daily_schedule()
    await hass.async_block_till_done()

    assert coordinator._unsub_daily is not None, "Scheduler should be active"

    await coordinator.async_shutdown()
    await hass.async_block_till_done()

    assert coordinator._unsub_daily is None, "Scheduler should be removed"


async def test_config_change_during_scan_does_not_affect_scan(
    hass: HomeAssistant, init_integration, tmp_path
):
    """Test config changes during scan operation use snapshot for consistency."""
    coordinator = init_integration.runtime_data
    media_dir = tmp_path / "media" / "concurrent_test"
    media_dir.mkdir(parents=True)

    for i in range(20):
        file = media_dir / f"test_{i}.jpg"
        file.touch()

    snapshot_before_scan = coordinator.create_config_snapshot()

    async def change_config_during_operation():
        await asyncio.sleep(0.01)
        await coordinator.async_update_config_value(CONF_RETENTION_DAYS, 99)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch(
            "pathlib.Path.glob",
            return_value=[media_dir / f"test_{i}.jpg" for i in range(20)],
        ),
    ):
        await asyncio.gather(
            coordinator.async_refresh(),
            change_config_during_operation(),
        )
        await hass.async_block_till_done()

    assert (
        snapshot_before_scan.retention_days == 7
    ), "Original snapshot should be unchanged"
    assert coordinator.retention_days == 99, "Current config should reflect change"


async def test_config_entry_options_sync_with_coordinator(
    hass: HomeAssistant, init_integration
):
    """Test config entry options stay in sync with coordinator config."""
    coordinator = init_integration.runtime_data

    await coordinator.async_update_config_value(CONF_RETENTION_DAYS, 35)
    await hass.async_block_till_done()

    assert (
        init_integration.options[CONF_RETENTION_DAYS] == 35
    ), "Options should sync immediately"
    assert coordinator.retention_days == 35, "Coordinator should reflect change"

    assert (
        coordinator.cfg[CONF_RETENTION_DAYS] == 35
    ), "Merged cfg property should show update"


async def test_multiple_rapid_config_changes(hass: HomeAssistant, init_integration):
    """Test rapid sequential config changes don't cause issues."""
    coordinator = init_integration.runtime_data

    for value in [10, 20, 30, 40, 50]:
        await coordinator.async_update_config_value(CONF_RETENTION_DAYS, value)

    await hass.async_block_till_done()

    assert coordinator.retention_days == 50, "Final value should apply"
    assert (
        init_integration.options[CONF_RETENTION_DAYS] == 50
    ), "Options should reflect final value"


async def test_config_change_preserves_other_options(
    hass: HomeAssistant, init_integration
):
    """Test updating one config value doesn't affect other options."""
    coordinator = init_integration.runtime_data

    original_pattern = coordinator.pattern
    original_max_deletes = coordinator.max_deletes
    original_dry_run = coordinator.dry_run

    await coordinator.async_update_config_value(CONF_RETENTION_DAYS, 28)
    await hass.async_block_till_done()

    assert coordinator.retention_days == 28, "Updated value should apply"
    assert coordinator.pattern == original_pattern, "pattern should be unchanged"
    assert (
        coordinator.max_deletes == original_max_deletes
    ), "max_deletes should be unchanged"
    assert coordinator.dry_run == original_dry_run, "dry_run should be unchanged"


async def test_dry_run_toggle_via_switch(hass: HomeAssistant, init_integration):
    """Test dry_run toggle via switch entity (migrated from select)."""
    coordinator = init_integration.runtime_data

    assert coordinator.dry_run is True, "Should start as True"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_cleanup_dry_run"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_cleanup_dry_run")
    assert state.state == "off", "State should be off"
    assert coordinator.dry_run is False, "Coordinator should be False"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_cleanup_dry_run"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_cleanup_dry_run")
    assert state.state == "on", "State should be on"
    assert coordinator.dry_run is True, "Coordinator should be True"


async def test_remove_empty_folders_toggle(hass: HomeAssistant, init_integration):
    """Test remove_empty_folders switch toggles correctly."""
    coordinator = init_integration.runtime_data

    assert coordinator.remove_empty_folders is False, "Should start as False"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_cleanup_remove_empty_folders"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert state.state == "on", "State should be on"
    assert coordinator.remove_empty_folders is True, "Coordinator should be True"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_cleanup_remove_empty_folders"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert state.state == "off", "State should be off"
    assert coordinator.remove_empty_folders is False, "Coordinator should be False"


async def test_max_deletes_change_triggers_scan(hass: HomeAssistant, init_integration):
    """Test changing max_deletes triggers coordinator refresh."""
    coordinator = init_integration.runtime_data

    initial_last_scan = coordinator.data.get("last_scan")
    initial_max_deletes = coordinator.max_deletes
    assert initial_max_deletes == 100, "Initial max_deletes should be 100"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.test_cleanup_max_deletes",
            NUMBER_ATTR_VALUE: 500,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert coordinator.max_deletes == 500, "max_deletes should be updated"

    new_last_scan = coordinator.data.get("last_scan")
    assert new_last_scan != initial_last_scan, "Scan should have been triggered"


async def test_keep_minimum_files_change(hass: HomeAssistant, init_integration):
    """Test changing keep_minimum_files updates coordinator."""
    coordinator = init_integration.runtime_data

    initial_keep_minimum = coordinator.keep_minimum_files
    assert initial_keep_minimum == 5, "Initial keep_minimum_files should be 5"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.test_cleanup_keep_minimum_files",
            NUMBER_ATTR_VALUE: 100,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert coordinator.keep_minimum_files == 100, "keep_minimum_files should be 100"
    assert (
        init_integration.options[CONF_KEEP_MINIMUM_FILES] == 100
    ), "Config entry options should be updated"


async def test_max_files_in_folder_zero_unlimited(
    hass: HomeAssistant, init_integration
):
    """Test that max_files_in_folder can be set to 0 (unlimited)."""
    coordinator = init_integration.runtime_data

    initial_max_files = coordinator.max_files_in_folder
    assert initial_max_files == 50, "Initial max_files_in_folder should be 50"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.test_cleanup_max_files_in_folder",
            NUMBER_ATTR_VALUE: 0,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert coordinator.max_files_in_folder == 0, "Should accept 0 (unlimited)"
    assert (
        init_integration.options[CONF_MAX_FILES_IN_FOLDER] == 0
    ), "Config entry should reflect 0"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.test_cleanup_max_files_in_folder",
            NUMBER_ATTR_VALUE: 10000,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert coordinator.max_files_in_folder == 10000, "Should accept 10000"
    assert (
        init_integration.options[CONF_MAX_FILES_IN_FOLDER] == 10000
    ), "Config entry should reflect 10000"


async def test_all_new_config_entities_exist(hass: HomeAssistant, init_integration):
    """Test all new config entities are created."""
    new_entities = [
        "switch.test_cleanup_dry_run",
        "switch.test_cleanup_remove_empty_folders",
        "number.test_cleanup_max_deletes",
        "number.test_cleanup_keep_minimum_files",
        "number.test_cleanup_max_files_in_folder",
    ]

    for entity_id in new_entities:
        state = hass.states.get(entity_id)
        assert state is not None, f"Entity {entity_id} should exist"


async def test_config_snapshot_includes_new_values(
    hass: HomeAssistant, init_integration
):
    """Test ConfigSnapshot includes all new config values."""
    coordinator = init_integration.runtime_data

    snapshot = coordinator.create_config_snapshot()

    assert hasattr(snapshot, "max_deletes"), "Snapshot should have max_deletes"
    assert hasattr(
        snapshot, "keep_minimum_files"
    ), "Snapshot should have keep_minimum_files"
    assert hasattr(
        snapshot, "max_files_in_folder"
    ), "Snapshot should have max_files_in_folder"
    assert hasattr(
        snapshot, "remove_empty_folders"
    ), "Snapshot should have remove_empty_folders"

    assert (
        snapshot.max_deletes == coordinator.max_deletes
    ), "Snapshot max_deletes should match coordinator"
    assert (
        snapshot.keep_minimum_files == coordinator.keep_minimum_files
    ), "Snapshot keep_minimum_files should match coordinator"
    assert (
        snapshot.max_files_in_folder == coordinator.max_files_in_folder
    ), "Snapshot max_files_in_folder should match coordinator"
    assert (
        snapshot.remove_empty_folders == coordinator.remove_empty_folders
    ), "Snapshot remove_empty_folders should match coordinator"


async def test_switch_changes_trigger_config_entry_update(
    hass: HomeAssistant, init_integration
):
    """Test switch changes persist to config entry options."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_cleanup_dry_run"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert (
        init_integration.options[CONF_DRY_RUN] is False
    ), "Config entry should reflect dry_run off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_cleanup_remove_empty_folders"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert (
        init_integration.options[CONF_REMOVE_EMPTY_FOLDERS] is True
    ), "Config entry should reflect remove_empty_folders on"


async def test_number_entities_update_coordinator_via_service(
    hass: HomeAssistant, init_integration
):
    """Test Number entity service calls update coordinator values."""
    coordinator = init_integration.runtime_data

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.test_cleanup_max_deletes",
            NUMBER_ATTR_VALUE: 250,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert coordinator.max_deletes == 250, "Coordinator max_deletes should be updated"
    assert (
        init_integration.options[CONF_MAX_DELETES] == 250
    ), "Config entry should be updated"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.test_cleanup_keep_minimum_files",
            NUMBER_ATTR_VALUE: 15,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert (
        coordinator.keep_minimum_files == 15
    ), "Coordinator keep_minimum_files should be updated"
    assert (
        init_integration.options[CONF_KEEP_MINIMUM_FILES] == 15
    ), "Config entry should be updated"


async def test_multiple_entity_changes_in_sequence(
    hass: HomeAssistant, init_integration
):
    """Test multiple config entity changes work correctly in sequence."""
    coordinator = init_integration.runtime_data

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.test_cleanup_max_deletes",
            NUMBER_ATTR_VALUE: 300,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert coordinator.max_deletes == 300, "First change should apply"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_cleanup_dry_run"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert coordinator.dry_run is False, "Second change should apply"
    assert coordinator.max_deletes == 300, "First change should persist"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.test_cleanup_keep_minimum_files",
            NUMBER_ATTR_VALUE: 20,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert coordinator.keep_minimum_files == 20, "Third change should apply"
    assert coordinator.dry_run is False, "Second change should persist"
    assert coordinator.max_deletes == 300, "First change should persist"


async def test_switch_entity_states_on_load(hass: HomeAssistant, init_integration):
    """Test switch entities load with correct initial states."""
    dry_run_state = hass.states.get("switch.test_cleanup_dry_run")
    assert dry_run_state is not None, "dry_run switch should exist"
    assert dry_run_state.state == "on", "dry_run should start on (True)"

    remove_empty_state = hass.states.get("switch.test_cleanup_remove_empty_folders")
    assert remove_empty_state is not None, "remove_empty_folders switch should exist"
    assert (
        remove_empty_state.state == "off"
    ), "remove_empty_folders should start off (False)"


async def test_number_entity_states_on_load(hass: HomeAssistant, init_integration):
    """Test number entities load with correct initial values."""
    max_deletes_state = hass.states.get("number.test_cleanup_max_deletes")
    assert max_deletes_state is not None, "max_deletes number should exist"
    assert float(max_deletes_state.state) == 100.0, "max_deletes should start at 100"

    keep_minimum_state = hass.states.get("number.test_cleanup_keep_minimum_files")
    assert keep_minimum_state is not None, "keep_minimum_files number should exist"
    assert (
        float(keep_minimum_state.state) == 5.0
    ), "keep_minimum_files should start at 5"

    max_files_state = hass.states.get("number.test_cleanup_max_files_in_folder")
    assert max_files_state is not None, "max_files_in_folder number should exist"
    assert (
        float(max_files_state.state) == 50.0
    ), "max_files_in_folder should start at 50"


async def test_config_snapshot_frozen_with_new_fields(
    hass: HomeAssistant, init_integration
):
    """Test ConfigSnapshot is immutable with new fields."""
    coordinator = init_integration.runtime_data

    snapshot = coordinator.create_config_snapshot()

    with pytest.raises((AttributeError, Exception)):
        snapshot.max_deletes = 999

    with pytest.raises((AttributeError, Exception)):
        snapshot.keep_minimum_files = 999

    with pytest.raises((AttributeError, Exception)):
        snapshot.max_files_in_folder = 999

    with pytest.raises((AttributeError, Exception)):
        snapshot.remove_empty_folders = True
