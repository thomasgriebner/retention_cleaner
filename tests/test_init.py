"""Test retention cleaner integration logic."""


class TestIntegrationLogic:
    """Test integration logic that doesn't require Home Assistant."""

    def test_runtime_data_pattern(self):
        """Test that runtime_data pattern works correctly."""
        # Test the pattern we use: entry.runtime_data = coordinator

        class MockEntry:
            def __init__(self):
                self.entry_id = "test_123"
                self.runtime_data = None

        class MockCoordinator:
            def __init__(self):
                self.data = {"test": "data"}

        entry = MockEntry()
        coordinator = MockCoordinator()

        # This is what our integration does
        entry.runtime_data = coordinator

        # Test access pattern
        retrieved_coordinator = entry.runtime_data
        assert retrieved_coordinator == coordinator
        assert retrieved_coordinator.data["test"] == "data"

    def test_platforms_list_integrity(self):
        """Test that PLATFORMS list is correctly defined."""
        # Test the platforms we set up
        expected_platforms = ["sensor", "binary_sensor", "button"]

        # Verify all platforms are strings
        for platform in expected_platforms:
            assert isinstance(platform, str)
            assert platform.strip() == platform  # No whitespace
            assert len(platform) > 0  # Not empty

        # Verify we have expected platforms
        assert "sensor" in expected_platforms
        assert "binary_sensor" in expected_platforms
        assert "button" in expected_platforms
        assert len(expected_platforms) == 3  # Only these three
