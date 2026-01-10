# Test Architecture Solution

## Overview
This document describes the improved test architecture for the retention_cleaner integration, solving the mock precedence issues and providing a more maintainable testing framework.

## Problem Statement
The original `init_integration` fixture mocked `Path.glob` to return `[]`, preventing exception handling tests from overriding this mock to raise exceptions. This caused test failures and prevented proper testing of error handling code paths.

## Solution Architecture

### 1. Refactored Fixture Base
Created a shared base function `_setup_integration_base()` that eliminates code duplication:

```python
async def _setup_integration_base(hass, entry, mock_glob=True, glob_return_value=None):
    """Shared integration setup logic with configurable mocking."""
```

**Benefits:**
- Single source of truth for integration setup
- Configurable mock behavior
- Reduced maintenance burden

### 2. Multiple Fixture Variants

#### Standard Fixture (`init_integration`)
- Uses default mocks including `Path.glob` returning `[]`
- Suitable for 90+ existing tests
- Maintains backward compatibility

#### No Glob Mock Fixture (`init_integration_no_glob_mock`)
- Skips `Path.glob` mocking
- Allows tests to control glob behavior
- Essential for exception handling tests

#### Exception Fixture (`init_integration_with_exception`)
- Pre-configured to raise exceptions
- Simplifies exception testing
- Can be parametrized for different exceptions

#### Configurable Fixture (`init_integration_configurable`)
- Highly flexible with multiple parameters
- Supports complex test scenarios
- Future-proof for new requirements

### 3. Test Helper Functions

Located in `conftest.py`, these helpers standardize common test patterns:

#### `assert_exception_chain()`
Verifies complete exception propagation chain:
```python
async def assert_exception_chain(operation, expected_error_type, expected_message)
```

#### `verify_cleanup_exception_handling()`
Specific helper for cleanup exception tests:
```python
async def verify_cleanup_exception_handling(coordinator, exception_to_raise)
```

#### `verify_scan_exception_handling()`
Specific helper for scan exception tests:
```python
async def verify_scan_exception_handling(coordinator, exception_to_raise)
```

**Benefits:**
- Consistent exception verification
- Reduced code duplication in tests
- Clear test intent

### 4. Improved Test Naming

Old naming convention (verbose):
- `test_general_exception_handling_in_async_operations`
- `test_directory_permission_errors_and_unexpected_exceptions`

New naming convention (concise):
- `test_cleanup_handles_filesystem_errors`
- `test_scan_handles_filesystem_errors`
- `test_scan_permission_denied`
- `test_cleanup_permission_denied`

**Benefits:**
- Better readability
- Clearer test purpose
- Easier navigation

### 5. Edge Case Testing

New test file `test_coordinator_edge_cases.py` covers:

#### Nested Exceptions
- Tests exception within exception handling
- Verifies proper error propagation

#### Timeout Scenarios
- Tests long-running operations
- Verifies timeout handling

#### Thread Safety
- Parallel operations testing
- Race condition verification

#### Critical Errors
- Disk full errors
- Memory errors
- System-level exceptions

#### Resource Cleanup
- Exception during shutdown
- Timer cleanup verification

## Usage Examples

### Basic Exception Test
```python
async def test_cleanup_handles_errors(init_integration_no_glob_mock):
    coordinator = init_integration_no_glob_mock.runtime_data

    exc_info = await verify_cleanup_exception_handling(
        coordinator,
        ValueError("Test error")
    )
    assert "Test error" in str(exc_info.value)
```

### Parametrized Exception Test
```python
@pytest.mark.parametrize(
    "init_integration_with_exception",
    [
        {"exception": PermissionError("No access")},
        {"exception": OSError("Disk error")},
    ],
    indirect=True
)
async def test_various_errors(init_integration_with_exception):
    # Test runs with each exception type
```

### Configurable Fixture Test
```python
@pytest.mark.parametrize(
    "init_integration_configurable",
    [{
        "mock_glob": True,
        "glob_return": [Mock(name="file.txt")],
        "mock_exists": False
    }],
    indirect=True
)
async def test_custom_scenario(init_integration_configurable):
    # Test with custom mock configuration
```

## Mock Strategy

### Module-Level Mocking
Always mock at the module level where the code uses it:
```python
patch("custom_components.retention_cleaner.coordinator.Path.glob")
```

NOT at the global level:
```python
patch("pathlib.Path.glob")  # Don't do this
```

### Mock Precedence Rules
1. Test-level patches override fixture-level patches
2. Inner context managers override outer ones
3. Later patches override earlier patches in same scope

## Best Practices

### 1. Choose the Right Fixture
- Use `init_integration` for standard tests
- Use `init_integration_no_glob_mock` for exception tests
- Use `init_integration_configurable` for complex scenarios

### 2. Use Helper Functions
- Prefer helpers over duplicating assertion logic
- Keep helpers in `conftest.py` for reusability

### 3. Clean Resource Management
Always cleanup in finally blocks:
```python
try:
    # Test code
finally:
    await coordinator.async_shutdown()
    await hass.async_block_till_done()
```

### 4. Test Real Code Paths
- Mock only filesystem operations
- Let coordinator logic execute
- Verify complete exception chains

### 5. Descriptive Test Names
- Start with component: `test_cleanup_*`, `test_scan_*`
- Describe behavior: `*_handles_errors`, `*_permission_denied`
- Keep concise but clear

## Migration Guide

### For Existing Tests
No changes required - existing tests using `init_integration` continue to work.

### For New Exception Tests
1. Use `init_integration_no_glob_mock` fixture
2. Mock at coordinator module level
3. Use helper functions for assertions
4. Follow new naming convention

### For Complex Tests
Consider using `init_integration_configurable` with parameters for maximum flexibility.

## Maintenance

### Adding New Fixtures
1. Extend `_setup_integration_base()` if possible
2. Document parameters clearly
3. Add usage examples in docstring

### Adding New Helpers
1. Place in `conftest.py`
2. Make generic and reusable
3. Include type hints and docstrings

### Updating Tests
1. Prefer helper functions over inline assertions
2. Use descriptive names
3. Group related tests together

## Benefits Summary

1. **Solved Mock Precedence Issue**: Exception tests now work correctly
2. **Backward Compatible**: No breaking changes to existing tests
3. **Maintainable**: Reduced duplication, clear patterns
4. **Flexible**: Multiple fixture variants for different needs
5. **Well-Documented**: Clear examples and guidelines
6. **Comprehensive**: Edge cases and thread safety covered
7. **Consistent**: Standardized patterns across all tests

## Future Improvements

1. **Performance Testing**: Add fixtures for benchmarking
2. **Integration Testing**: Add fixtures for full E2E tests
3. **Snapshot Testing**: Consider adding snapshot comparisons
4. **Property-Based Testing**: Use hypothesis for edge cases
5. **Test Coverage Reporting**: Automated coverage tracking
