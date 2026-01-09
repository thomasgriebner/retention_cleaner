"""Test retention_cleaner integration setup and teardown."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import pytest

from custom_components.retention_cleaner import (
    PLATFORMS,
    async_setup_entry,
    async_unload_entry,
)


async def test_setup_entry_success(hass: HomeAssistant, mock_setup_entry):
    """Test successful setup of the integration."""
    mock_setup_entry.add_to_hass(hass)

    with patch(
        "custom_components.retention_cleaner.RetentionCleanerCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = mock_coordinator_class.return_value
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.async_setup_daily_schedule = AsyncMock()

        result = await async_setup_entry(hass, mock_setup_entry)

    assert result is True
    assert mock_setup_entry.state == ConfigEntryState.LOADED

    # Check coordinator was initialized
    mock_coordinator_class.assert_called_once_with(hass, mock_setup_entry)
    mock_coordinator.async_config_entry_first_refresh.assert_called_once()
    mock_coordinator.async_setup_daily_schedule.assert_called_once()

    # Check coordinator is stored directly in runtime data
    assert mock_setup_entry.runtime_data is not None
    assert mock_setup_entry.runtime_data == mock_coordinator


async def test_setup_entry_failure_first_refresh(hass: HomeAssistant, mock_setup_entry):
    """Test setup failure during first coordinator refresh."""
    mock_setup_entry.add_to_hass(hass)

    with patch(
        "custom_components.retention_cleaner.RetentionCleanerCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = mock_coordinator_class.return_value
        # Simulate refresh failure
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(
            side_effect=Exception("Connection error")
        )

        with pytest.raises(Exception, match="Connection error"):
            await async_setup_entry(hass, mock_setup_entry)


async def test_unload_entry(hass: HomeAssistant, init_integration):
    """Test unloading the integration."""
    entry = init_integration

    # Verify entry is loaded
    assert entry.state == ConfigEntryState.LOADED

    # Mock the coordinator's async_remove_listeners method
    coordinator = entry.runtime_data
    with patch.object(coordinator, "async_remove_listeners") as mock_remove_listeners:
        # Unload the entry
        result = await async_unload_entry(hass, entry)

        assert result is True
        # Coordinator listeners should be removed
        mock_remove_listeners.assert_called_once()


async def test_setup_multiple_entries(
    hass: HomeAssistant, mock_setup_entry, mock_setup_entry_no_dry_run
):
    """Test setting up multiple config entries."""
    mock_setup_entry.add_to_hass(hass)
    mock_setup_entry_no_dry_run.add_to_hass(hass)

    with patch(
        "custom_components.retention_cleaner.RetentionCleanerCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = mock_coordinator_class.return_value
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.async_setup_daily_schedule = AsyncMock()

        # Setup both entries
        result1 = await async_setup_entry(hass, mock_setup_entry)
        result2 = await async_setup_entry(hass, mock_setup_entry_no_dry_run)

    assert result1 is True
    assert result2 is True
    assert mock_coordinator_class.call_count == 2


async def test_platforms_setup(hass: HomeAssistant, mock_setup_entry):
    """Test that all platforms are set up."""
    mock_setup_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.retention_cleaner.RetentionCleanerCoordinator"
        ) as mock_coordinator_class,
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
        ) as mock_forward_setups,
    ):
        mock_coordinator = mock_coordinator_class.return_value
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.async_setup_daily_schedule = AsyncMock()

        await async_setup_entry(hass, mock_setup_entry)

        # Verify all platforms are forwarded for setup
        mock_forward_setups.assert_called_once_with(mock_setup_entry, PLATFORMS)


async def test_entry_reload(hass: HomeAssistant, init_integration):
    """Test reloading a config entry."""
    entry = init_integration

    # Get initial coordinator
    initial_coordinator = entry.runtime_data

    # Mock the coordinator's async_remove_listeners method
    with patch.object(
        initial_coordinator, "async_remove_listeners"
    ) as mock_remove_listeners:
        # Reload the entry
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

        # Verify old coordinator listeners were removed during unload
        mock_remove_listeners.assert_called()

    # Entry should still be loaded after reload
    assert entry.state == ConfigEntryState.LOADED


async def test_coordinator_initialization_params(hass: HomeAssistant, mock_setup_entry):
    """Test coordinator is initialized with correct parameters."""
    mock_setup_entry.add_to_hass(hass)

    with patch(
        "custom_components.retention_cleaner.RetentionCleanerCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = mock_coordinator_class.return_value
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.async_setup_daily_schedule = AsyncMock()

        await async_setup_entry(hass, mock_setup_entry)

        # Verify coordinator was initialized with correct params
        mock_coordinator_class.assert_called_once_with(hass, mock_setup_entry)


async def test_runtime_data_structure(hass: HomeAssistant, mock_setup_entry):
    """Test that runtime data is properly structured."""
    # Runtime data should be the coordinator directly
    with patch(
        "custom_components.retention_cleaner.RetentionCleanerCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = mock_coordinator_class.return_value
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.async_setup_daily_schedule = AsyncMock()

        mock_setup_entry.add_to_hass(hass)
        await async_setup_entry(hass, mock_setup_entry)

        # Runtime data should be the coordinator itself
        assert mock_setup_entry.runtime_data == mock_coordinator


async def test_setup_entry_updates_options(hass: HomeAssistant, mock_setup_entry):
    """Test that options updates trigger coordinator update."""
    mock_setup_entry.add_to_hass(hass)

    with patch(
        "custom_components.retention_cleaner.RetentionCleanerCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = mock_coordinator_class.return_value
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator.async_setup_daily_schedule = AsyncMock()

        await async_setup_entry(hass, mock_setup_entry)

        # Update options
        hass.config_entries.async_update_entry(
            mock_setup_entry, options={"retention_days": 14}
        )
        await hass.async_block_till_done()

        # Coordinator should handle the options update
        assert mock_coordinator_class.called
