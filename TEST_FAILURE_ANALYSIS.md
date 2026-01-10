# Test Failure Analysis - Coordinator Exception Handling

## Current Status
**2 Tests Failing** (Out of 79 total tests)
- `test_general_exception_handling_in_async_operations`
- `test_directory_permission_errors_and_unexpected_exceptions`

**Coverage**: 88.71% (Goal: 90%+)

---

## Failing Tests Analysis

### Test 1: `test_general_exception_handling_in_async_operations`
**Error**: `AttributeError: 'dict' object has no attribute 'deleted'`
**Root Cause**: The test expects a `CleanupResult` object but gets a dict instead

### Test 2: `test_directory_permission_errors_and_unexpected_exceptions`
**Error**: `Failed: DID NOT RAISE <class 'homeassistant.helpers.update_coordinator.UpdateFailed'>`
**Root Cause**: The exception is not being raised, meaning our mock override isn't working

---

## Historical Analysis - What We've Tried

### Commit History Analysis
Based on recent commits, we have attempted multiple strategies:

#### 1. **Manual Coordinator Creation** (Commit: e00d459)
- **Approach**: Created coordinator manually with `RetentionCleanerCoordinator(hass, config_entry)`
- **Problem**: Coordinator wasn't properly initialized within HA context
- **Result**: Failed - coordinator behavior was inconsistent

#### 2. **Path Instance Method Mocking** (Commit: e00d459)
- **Approach**: Used `patch.object(Path, "glob", ...)` to mock instance methods
- **Problem**: Still conflicted with fixture mocks
- **Result**: Failed - exceptions not triggered

#### 3. **Filesystem-Only Mocking Strategy** (Commit: 9d5b08d)
- **Approach**: Mock only filesystem operations, let real coordinator logic run
- **Problem**: Mock precedence issues with `init_integration` fixture
- **Result**: Partially successful but still failing

#### 4. **Debugging with Extensive Logging** (Commit: 2a7968f)
- **Approach**: Added comprehensive logging to understand mock and coordinator behavior
- **Problem**: Logs showed mocks were called but exceptions weren't propagating
- **Result**: Identified mock precedence as core issue

#### 5. **Step-by-Step Verification** (Commit: 3852e1b)
- **Approach**: Simplified tests to verify each step of the exception chain
- **Problem**: Lost the real code testing aspect
- **Result**: Tests passed but weren't testing actual production code

#### 6. **Mock Override with patch()** (Commit: 8682f8d - Current)
- **Approach**: Use `patch("pathlib.Path.glob", side_effect=Exception)` to override fixture
- **Problem**: Still failing - mock override not working as expected
- **Result**: Current failing state

---

## Core Problem: Mock Precedence Conflict

### The `init_integration` Fixture Issue
Located in `conftest.py` lines 64-68:
```python
with (
    patch("pathlib.Path.exists", return_value=True),
    patch("pathlib.Path.is_dir", return_value=True),
    patch("pathlib.Path.glob", return_value=[]),  # ← PROBLEM
):
```

**The Issue**: This fixture mocks `Path.glob` to return `[]` empty list. When our tests try to mock `Path.glob` to raise exceptions, the precedence conflict means exceptions never get raised.

### Exception Chain We Want to Test
1. `coordinator.async_run_cleanup_now()` → `asyncio.to_thread(_cleanup_folder, ...)`
2. `_cleanup_folder` line 292: `for p in base.glob(pattern):` → **Exception here**
3. Line 378: `except Exception as e:` catches it
4. Line 379: `raise RuntimeError(f"Cleanup failed: {e!s}") from e`
5. Coordinator line 620: `except Exception as e:` catches RuntimeError
6. Line 623: `raise UpdateFailed(str(e)) from e`

---

## Principles for Test Development

### What We WANT to Achieve
1. **Test Real Code Paths**: Exercise actual coordinator and _cleanup_folder/_scan_folder logic
2. **Minimal Mocking**: Only mock filesystem operations, not HA infrastructure
3. **Complete Exception Chain Testing**: Verify filesystem error → RuntimeError → UpdateFailed
4. **Proper Resource Cleanup**: Use `async_shutdown()` to prevent lingering timers
5. **Integration Context**: Use `init_integration` fixture for proper HA setup

### What We MUST Avoid
1. **Over-mocking**: Don't mock coordinator methods or HA framework
2. **Manual Coordinator Creation**: Don't bypass proper HA integration setup
3. **Mock Coordinator Behavior**: Don't test mocks instead of real code
4. **Ignoring Fixture Conflicts**: Can't ignore the `init_integration` fixture mocks
5. **Race Conditions**: Must handle async timing properly with `async_block_till_done()`

### Test Development Rules
1. **Use `init_integration` fixture** - Required for proper HA context
2. **Override fixture mocks correctly** - Must achieve higher precedence than fixture
3. **Test exception propagation** - Verify complete error handling chain
4. **Maintain async patterns** - Proper await and cleanup patterns
5. **No redundant comments** - Code should be self-documenting

---

## Technical Constraints

### Mock Precedence Rules
- Context manager precedence: Inner context managers override outer ones
- Patch precedence: Later patches override earlier patches in same scope
- Fixture scope: Test-level patches should override fixture-level patches

### Home Assistant Testing Constraints
- **Integration setup**: Must use proper config entry setup via `hass.config_entries.async_setup()`
- **Coordinator lifecycle**: Must call `async_config_entry_first_refresh()` or `async_refresh()` appropriately
- **Resource cleanup**: Must clean up timers and async tasks
- **Async timing**: Must wait for operations with `await hass.async_block_till_done()`

---

## Current Hypothesis: Why Tests Still Fail

### Test 1 Failure Analysis
```
AttributeError: 'dict' object has no attribute 'deleted'
```
**Possible Causes**:
1. `async_run_cleanup_now()` might return coordinator data dict instead of CleanupResult
2. Exception path might return different data structure
3. Mock might be preventing proper CleanupResult creation

### Test 2 Failure Analysis
```
Failed: DID NOT RAISE <class 'UpdateFailed'>
```
**Possible Causes**:
1. Mock override still not working - fixture precedence issue persists
2. Exception path might not be reached due to early returns
3. Exception might be caught and handled differently than expected
4. `async_run_scan_now()` might have different exception handling than `async_run_cleanup_now()`

---

## Next Steps Strategy

### Immediate Investigation Needed
1. **Verify Mock Override**: Check if our `patch()` actually overrides fixture mock
2. **Trace Execution Path**: Add debugging to see exactly where execution goes
3. **Check Return Types**: Verify what `async_run_cleanup_now()` actually returns on exception
4. **Test scan vs cleanup**: Verify both methods have same exception handling pattern

### Alternative Approaches to Consider
1. **Bypass init_integration fixture**: Create custom fixture without Path.glob mock
2. **Test sync functions directly**: Test `_cleanup_folder` and `_scan_folder` directly
3. **Integration-level testing**: Test through HA service calls instead of coordinator methods
4. **Separate fixtures**: Create exception-testing specific fixtures

### Success Criteria
- Both tests pass consistently
- Tests exercise real production code paths (not just mocks)
- Complete exception chain verified: filesystem → RuntimeError → UpdateFailed
- Coverage reaches 90%+
- Resource cleanup prevents lingering timer errors

---

## Current Code State

The tests are currently in `tests/test_coordinator.py` attempting the **Mock Override with patch()** strategy. Based on commit history and current failures, this approach is not yet working correctly.

**Key Files**:
- `tests/conftest.py` - Contains problematic `init_integration` fixture
- `tests/test_coordinator.py` - Contains failing tests
- `custom_components/retention_cleaner/coordinator.py` - Production code being tested
