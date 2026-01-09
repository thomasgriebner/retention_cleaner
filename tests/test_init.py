"""Test retention cleaner integration setup and teardown."""
import pytest
from unittest.mock import AsyncMock, Mock, patch

# Test the integration setup without HA dependencies


class TestIntegrationSetup:
    """Test integration setup and unload functions."""

    @pytest.mark.asyncio
    async def test_async_setup_yaml_not_supported(self):
        """Test that YAML setup returns True (not supported)."""
        # Import here to avoid HA dependency issues
        try:
            from custom_components.retention_cleaner import async_setup
        except ImportError:
            pytest.skip("Home Assistant not available")
            
        mock_hass = Mock()
        mock_config = {}
        
        result = await async_setup(mock_hass, mock_config)
        assert result is True

    @pytest.mark.asyncio 
    async def test_async_setup_entry_success(self, mock_hass, mock_config_entry_obj):
        """Test successful config entry setup."""
        with patch('custom_components.retention_cleaner.RetentionCleanerCoordinator') as mock_coordinator_class:
            # Setup coordinator mock
            mock_coordinator = Mock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator.async_setup_daily_schedule = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator
            
            # Import function under test
            try:
                from custom_components.retention_cleaner import async_setup_entry
            except ImportError:
                pytest.skip("Home Assistant not available")
            
            # Call function
            result = await async_setup_entry(mock_hass, mock_config_entry_obj)
            
            # Assertions
            assert result is True
            
            # Verify coordinator was created and configured
            mock_coordinator_class.assert_called_once_with(mock_hass, mock_config_entry_obj)
            mock_coordinator.async_config_entry_first_refresh.assert_called_once()
            mock_coordinator.async_setup_daily_schedule.assert_called_once()
            
            # Verify hass.data was set up correctly
            assert "retention_cleaner" in mock_hass.data
            assert mock_config_entry_obj.entry_id in mock_hass.data["retention_cleaner"]
            assert mock_hass.data["retention_cleaner"][mock_config_entry_obj.entry_id] == mock_coordinator
            
            # Verify platforms were set up
            mock_hass.config_entries.async_forward_entry_setups.assert_called_once_with(
                mock_config_entry_obj, ["sensor", "binary_sensor", "button"]
            )

    @pytest.mark.asyncio
    async def test_async_unload_entry_success(self, mock_hass, mock_config_entry_obj):
        """Test successful config entry unload."""
        # Setup hass.data with coordinator
        mock_coordinator = Mock()
        mock_coordinator.async_remove_listeners = Mock()
        
        mock_hass.data = {
            "retention_cleaner": {
                mock_config_entry_obj.entry_id: mock_coordinator
            }
        }
        
        try:
            from custom_components.retention_cleaner import async_unload_entry
        except ImportError:
            pytest.skip("Home Assistant not available")
        
        # Call function 
        result = await async_unload_entry(mock_hass, mock_config_entry_obj)
        
        # Assertions
        assert result is True
        
        # Verify coordinator cleanup was called
        mock_coordinator.async_remove_listeners.assert_called_once()
        
        # Verify platforms were unloaded
        mock_hass.config_entries.async_unload_platforms.assert_called_once_with(
            mock_config_entry_obj, ["sensor", "binary_sensor", "button"]
        )
        
        # Verify data cleanup
        assert mock_config_entry_obj.entry_id not in mock_hass.data["retention_cleaner"]

    @pytest.mark.asyncio
    async def test_async_unload_entry_no_coordinator(self, mock_hass, mock_config_entry_obj):
        """Test unload when no coordinator exists in hass.data."""
        # Empty hass.data
        mock_hass.data = {}
        
        try:
            from custom_components.retention_cleaner import async_unload_entry
        except ImportError:
            pytest.skip("Home Assistant not available")
        
        # Call function
        result = await async_unload_entry(mock_hass, mock_config_entry_obj)
        
        # Should still succeed
        assert result is True
        
        # Platforms should still be unloaded
        mock_hass.config_entries.async_unload_platforms.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_unload_entry_platform_failure(self, mock_hass, mock_config_entry_obj):
        """Test unload when platform unloading fails."""
        # Setup coordinator
        mock_coordinator = Mock()
        mock_hass.data = {
            "retention_cleaner": {
                mock_config_entry_obj.entry_id: mock_coordinator
            }
        }
        
        # Make platform unload fail
        mock_hass.config_entries.async_unload_platforms.return_value = False
        
        try:
            from custom_components.retention_cleaner import async_unload_entry
        except ImportError:
            pytest.skip("Home Assistant not available")
        
        # Call function
        result = await async_unload_entry(mock_hass, mock_config_entry_obj)
        
        # Should return False
        assert result is False
        
        # Data should NOT be cleaned up when unload fails
        assert mock_config_entry_obj.entry_id in mock_hass.data["retention_cleaner"]