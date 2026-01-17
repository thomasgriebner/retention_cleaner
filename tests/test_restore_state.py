"""Test state restoration for retention cleaner sensors."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_restore_state_shutdown_restart,
)


async def test_binary_sensor_restore_on_state(hass: HomeAssistant):
    """Test binary sensor restores 'on' state correctly."""
    entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
            "dry_run": True,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_entry_binary_1",
    )
    entry.add_to_hass(hass)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data

    coordinator.data = {"path_available": True}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_cleanup_path_available")
    assert state is not None
    assert state.state == "on"

    await async_mock_restore_state_shutdown_restart(hass)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    coordinator.data = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_cleanup_path_available")
    assert state is not None
    assert state.state == "on"


async def test_binary_sensor_current_data_overrides_restored(hass: HomeAssistant):
    """Test that current coordinator data overrides restored state for binary sensor."""
    entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
            "dry_run": True,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_entry_binary_2",
    )
    entry.add_to_hass(hass)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data

    coordinator.data = {"path_available": False}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_cleanup_path_available")
    assert state is not None
    assert state.state == "off"

    await async_mock_restore_state_shutdown_restart(hass)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    coordinator.data = {"path_available": False}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_cleanup_path_available")
    assert state is not None
    assert state.state == "off"


async def test_restoration_exception_handling(hass: HomeAssistant):
    """Test graceful handling of restoration failures."""
    entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
            "dry_run": True,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_entry_exception",
    )
    entry.add_to_hass(hass)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data

    coordinator.data = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state is not None


async def test_sensor_timestamp_parsing_failures(hass: HomeAssistant):
    """Test timestamp sensors handle invalid timestamp strings gracefully."""
    from homeassistant.core import State

    entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
            "dry_run": True,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_timestamp_parse",
    )
    entry.add_to_hass(hass)

    mock_state = State(
        entity_id="sensor.test_cleanup_last_scan",
        state="not-a-valid-timestamp",
        attributes={},
    )

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
        patch(
            "homeassistant.helpers.restore_state.RestoreEntity.async_get_last_state",
            return_value=mock_state,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    coordinator.data = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_last_scan")
    assert state is not None
    assert state.state in ("unknown", "unavailable")


async def test_sensor_numeric_string_digit_conversion(hass: HomeAssistant):
    """Test numeric sensors convert string digits correctly."""
    from homeassistant.core import State

    entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
            "dry_run": True,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_numeric_string",
    )
    entry.add_to_hass(hass)

    mock_state = State(
        entity_id="sensor.test_cleanup_total_files",
        state="12345",
        attributes={},
    )

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
        patch(
            "homeassistant.helpers.restore_state.RestoreEntity.async_get_last_state",
            return_value=mock_state,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    coordinator.data = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state is not None
    assert state.state == "12345"


async def test_sensor_numeric_int_float_conversion(hass: HomeAssistant):
    """Test numeric sensors handle int and float types correctly."""
    entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
            "dry_run": True,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_numeric_types",
    )
    entry.add_to_hass(hass)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data

    coordinator.data = {"total_files": 42}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state is not None
    assert state.state == "42"

    await async_mock_restore_state_shutdown_restart(hass)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    coordinator.data = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state is not None
    assert state.state == "42"


async def test_sensor_numeric_invalid_type_fallback(hass: HomeAssistant):
    """Test numeric sensors fall back to 0 for invalid types."""
    from homeassistant.core import State

    entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
            "dry_run": True,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_numeric_invalid",
    )
    entry.add_to_hass(hass)

    mock_state = State(
        entity_id="sensor.test_cleanup_total_files",
        state="not-a-number",
        attributes={},
    )

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
        patch(
            "homeassistant.helpers.restore_state.RestoreEntity.async_get_last_state",
            return_value=mock_state,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    coordinator.data = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state is not None
    assert state.state == "0"


async def test_sensor_timestamp_datetime_object_restoration(hass: HomeAssistant):
    """Test timestamp sensor restores datetime object directly."""
    from unittest.mock import MagicMock

    entry = MockConfigEntry(
        domain="retention_cleaner",
        title="Test Cleanup",
        data={
            "base_path": "/media/test",
            "pattern": "*.jpg",
            "retention_days": 7,
            "dry_run": True,
            "max_deletes": 100,
            "run_at": "02:00",
        },
        entry_id="test_timestamp_datetime",
    )
    entry.add_to_hass(hass)

    test_datetime = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
    mock_state = MagicMock()
    mock_state.state = test_datetime
    mock_state.attributes = {}

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", return_value=[]),
        patch(
            "homeassistant.helpers.restore_state.RestoreEntity.async_get_last_state",
            return_value=mock_state,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    coordinator.data = {}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_last_scan")
    assert state is not None
    assert state.state == "2024-01-15T10:30:00+00:00"
