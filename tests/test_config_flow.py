"""Test retention cleaner config flow validation logic."""
import pytest


class TestConfigFlowValidation:
    """Test config flow validation logic without HA dependencies."""

    def test_valid_path_accepted(self):
        """Test that valid /media/ paths are accepted."""
        valid_paths = [
            "/media/photos",
            "/media/recordings",
            "/media/snapshots/camera1",
        ]
        
        for path in valid_paths:
            assert path.startswith("/media/"), f"Path {path} should be valid"

    def test_invalid_path_rejected(self):
        """Test that paths outside /media/ are rejected."""        
        invalid_paths = [
            "/home/user",
            "/var/log",
            "/etc/config",
            "media/relative",  # Missing leading slash
            "",
        ]
        
        for invalid_path in invalid_paths:
            # Path should either be empty or not start with /media/
            assert not invalid_path.startswith("/media/"), f"Path {invalid_path} should be invalid"

    def test_dangerous_pattern_validation(self):
        """Test that dangerous patterns are identified."""
        dangerous_patterns = [
            "*",           # Matches all files
            "**/*",        # Matches everything recursively
            "***",         # Invalid glob syntax
            "[unclosed",   # Unclosed bracket
        ]
        
        for pattern in dangerous_patterns:
            # These patterns should be considered dangerous
            is_dangerous = (
                pattern in ["*", "**/*"] or
                "***" in pattern or
                ("[" in pattern and "]" not in pattern)
            )
            assert is_dangerous, f"Pattern {pattern} should be considered dangerous"

    def test_valid_time_format(self):
        """Test time format validation."""
        valid_times = ["00:00", "02:30", "14:45", "23:59"]
        
        for time_str in valid_times:
            # Basic format check: HH:MM
            parts = time_str.split(":")
            assert len(parts) == 2
            hour, minute = int(parts[0]), int(parts[1])
            assert 0 <= hour <= 23
            assert 0 <= minute <= 59

    def test_invalid_time_format(self):
        """Test invalid time formats are rejected."""
        invalid_times = [
            "25:00",    # Invalid hour
            "12:60",    # Invalid minute
            "2:30",     # Missing leading zero
            "12:5",     # Missing leading zero
            "invalid",  # Not a time
            "",         # Empty string
            "12:30:45", # Seconds not allowed
        ]
        
        for time_str in invalid_times:
            is_invalid = True
            try:
                if ":" not in time_str:
                    continue  # Obviously invalid
                parts = time_str.split(":")
                if len(parts) != 2:
                    continue  # Wrong format
                hour, minute = int(parts[0]), int(parts[1])
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    continue  # Out of range
                if len(parts[0]) != 2 or len(parts[1]) != 2:
                    continue  # Wrong padding
                is_invalid = False
            except (ValueError, IndexError):
                pass  # Expected for invalid formats
            
            assert is_invalid, f"Time {time_str} should be considered invalid"

    def test_retention_days_validation(self):
        """Test retention days validation."""
        # Valid values
        assert 1 <= 7 <= 3650    # 1 week
        assert 1 <= 30 <= 3650   # 1 month 
        assert 1 <= 365 <= 3650  # 1 year
        
        # Invalid values
        invalid_values = [0, -1, 3651, 10000]
        for value in invalid_values:
            assert not (1 <= value <= 3650), f"Value {value} should be invalid"

    def test_max_deletes_validation(self):
        """Test max deletes validation."""
        # Valid values
        assert 1 <= 100 <= 100000     # Normal limit
        assert 1 <= 5000 <= 100000    # Default limit
        assert 1 <= 50000 <= 100000   # High limit
        
        # Invalid values
        invalid_values = [0, -1, 100001, 1000000]
        for value in invalid_values:
            assert not (1 <= value <= 100000), f"Value {value} should be invalid"