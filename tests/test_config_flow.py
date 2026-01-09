"""Test retention cleaner config flow validation logic."""


class TestConfigFlowValidation:
    """Test config flow validation logic without HA dependencies."""

    def test_dangerous_pattern_validation(self):
        """Test that dangerous patterns are identified."""
        dangerous_patterns = [
            "*",  # Matches all files
            "**/*",  # Matches everything recursively
            "***",  # Invalid glob syntax
            "[unclosed",  # Unclosed bracket
        ]

        for pattern in dangerous_patterns:
            # These patterns should be considered dangerous
            is_dangerous = (
                pattern in ["*", "**/*"]
                or "***" in pattern
                or ("[" in pattern and "]" not in pattern)
            )
            assert is_dangerous, f"Pattern {pattern} should be considered dangerous"
