"""Test state restoration for retention cleaner sensors."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_restore_state_shutdown_restart,
)

from homeassistant.core import HomeAssistant

import custom_components.retention_cleaner


async def test_sensor_restore_numeric_value(hass: HomeAssistant):
    """Test sensor restores numeric values correctly."""
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
        entry_id="test_entry_123",
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

    coordinator.data = {
        "total_files": 42,
        "base_path": "/media/test",
        "pattern": "*.jpg",
        "retention_days": 7,
    }
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


async def test_sensor_restore_timestamp_value(hass: HomeAssistant):
    """Test sensor restores timestamp values correctly."""
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
        entry_id="test_entry_456",
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

    test_timestamp = datetime(2024, 1, 7, 15, 30, 45, tzinfo=UTC)
    coordinator.data = {
        "last_scan": test_timestamp,
        "base_path": "/media/test",
        "pattern": "*.jpg",
        "retention_days": 7,
    }
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_last_scan")
    assert state is not None
    assert state.state == "2024-01-07T15:30:45+00:00"

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

    state = hass.states.get("sensor.test_cleanup_last_scan")
    assert state is not None
    assert state.state == "2024-01-07T15:30:45+00:00"


async def test_sensor_current_data_overrides_restored(hass: HomeAssistant):
    """Test that current coordinator data overrides restored state."""
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
        entry_id="test_entry_789",
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
    coordinator.data = {"total_files": 123}
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_cleanup_total_files")
    assert state is not None
    assert state.state == "123"


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
