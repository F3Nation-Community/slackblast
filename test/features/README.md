# Preblast Tests

This directory contains tests for the preblast functionality in slackblast.

## Test Files

### `test_preblast_pytest.py`
Pytest-compatible tests for the same functionality, organized into test classes.

**Run with:**
```bash
# Install pytest first if not available
pip install pytest

# Run all tests
pytest test/features/test_preblast_pytest.py -v

# Run specific test class
pytest test/features/test_preblast_pytest.py::TestPreblastMessageFormatting -v

# Run with coverage (if pytest-cov is installed)
pytest test/features/test_preblast_pytest.py --cov=slackblast.features.preblast
```

### `test_preblast.py` 
A more comprehensive test file that attempts to import and mock the actual preblast functions. May require more dependencies to be installed.

## What's Tested

The tests cover the following functionality from `preblast.py`:

1. **Message Formatting**
   - Formatting preblast messages with all fields
   - Formatting with minimal required fields only
   - Proper handling of optional fields (why, coupons, fngs)

2. **Edit Permissions**
   - Admin users can always edit
   - Original Q can edit their preblast
   - Original poster can edit their preblast  
   - Anyone can edit when editing is unlocked
   - Proper denial when user lacks permissions

3. **Destination Routing**
   - Routing to AO channel when "The_AO" is selected
   - Routing to user DMs when user ID is specified

4. **Slack Block Structure**
   - Proper creation of message blocks
   - Inclusion of action buttons (Edit/New)
   - Handling of optional moleskin blocks

5. **Form Mode Detection**
   - Detecting create vs edit mode from request body
   - Handling different input sources (slash command, buttons, etc.)

6. **Safe Dictionary Access**
   - Safe access to nested dictionary values
   - Proper handling of missing keys
   - Graceful handling of non-dict values

## Benefits of These Tests

- **Documentation**: Tests serve as living documentation showing how the preblast functions work
- **Regression Prevention**: Catch bugs when making changes to the preblast logic
- **Edge Case Coverage**: Test various scenarios including error conditions
- **Refactoring Safety**: Confidence when refactoring knowing tests will catch breaking changes
- **New Developer Onboarding**: Help new developers understand expected behavior

## Adding More Tests

When adding new preblast functionality:

1. Add corresponding test cases to cover the new logic
2. Include both positive and negative test cases  
3. Test edge cases and error conditions
4. Update this README if new test categories are added

## Dependencies

The standalone tests require only standard Python libraries. The pytest version requires:
- `pytest` for running tests
- `unittest.mock` (built into Python 3.3+)

The full integration tests may require the actual slackblast dependencies. 