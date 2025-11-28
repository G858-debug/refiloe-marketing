# Avatar Looks System Test Suite

Comprehensive end-to-end test suite for the avatar looks generation system.

## Overview

This test suite validates the complete avatar looks generation system including:

- **10 look definitions** in `looks_generator.py`
- **Content type detection** and look selection in `avatar_mapping.py`
- **Weekly avatar generation job** in `scheduler.py`
- **Database operations** for storing and retrieving looks
- **API payload structure** for HeyGen integration

## Quick Start

```bash
# Run all tests in dry-run mode (no API calls)
./tests/run_tests.sh

# Run with verbose output
./tests/run_tests.sh -v

# Run only unit tests
./tests/run_tests.sh --unit

# Run only integration tests
./tests/run_tests.sh --integration

# Run quick validation tests
./tests/run_tests.sh --quick
```

## Test Categories

### 1. Unit Tests

#### Look Definitions (`TestLookDefinitions`)
- Validates all 10 look definitions are present
- Checks required fields (name, description, prompt, environment, attire, mood)
- Verifies prompt length and quality
- Tests `get_available_looks()` and `get_look_details()`

#### Content Type Detection (`TestContentTypeDetection`)
- Tests detection of workout, fitness, professional, motivational content
- Validates explicit content_type parameter override
- Checks default look assignment for unknown content
- Tests look_id passthrough

#### Avatar Selection (`TestAvatarSelection`)
- Tests avatar ID selection for different content types
- Validates combined avatar and look selection
- Checks all avatar IDs have valid format

#### API Payload Generation (`TestAPIPayloadGeneration`)
- Validates look generation payload structure
- Tests motion addition payload structure
- Verifies custom prompt override behavior

#### Database Operations (`TestDatabaseOperations`)
- Tests save_look_to_database functionality
- Tests get_saved_looks with various filters
- Validates error handling for missing Supabase client

### 2. Integration Tests

#### Full Flow (`TestIntegrationFlow`)
- Tests complete: content -> look selection -> generation request
- Validates avatar_mapping integration with looks_generator
- Tests look ID storage and retrieval

#### Scheduler Integration (`TestSchedulerIntegration`)
- Tests weekly avatar job theme rotation
- Validates scheduler job registration
- Tests dry-run mode for weekly job

### 3. Validation Tests

#### Environment (`TestEnvironmentValidation`)
- Validates required environment variables
- Tests LooksGenerator API key validation
- Checks group ID validation

#### Error Handling (`TestErrorHandling`)
- Tests invalid look type error
- Tests empty motion prompt error
- Tests API failure handling

### 4. Backward Compatibility Tests

Ensures new code doesn't break existing functionality:
- Avatar mapping still returns valid IDs
- Content type detection alignment
- Video generation imports work

### 5. Deployment Readiness Tests

- Validates deployment checklist coverage
- Tests HeyGen API authentication (with live credentials)
- Tests Supabase connection (with live credentials)

## Running Tests

### Dry-Run Mode (Default)

Tests run without making real API calls. All external calls are mocked.

```bash
# Using shell script
./tests/run_tests.sh

# Using pytest directly
pytest tests/test_avatar_looks_system.py -v
```

### Live Mode

Tests make real API calls. Requires valid credentials.

```bash
# Set environment variables
export HEYGEN_API_KEY="your_api_key"
export HEYGEN_PHOTO_AVATAR_GROUP_ID="your_group_id"
export SUPABASE_URL="your_supabase_url"
export SUPABASE_ANON_KEY="your_supabase_key"

# Run with live APIs
./tests/run_tests.sh --live

# Or with pytest
pytest tests/test_avatar_looks_system.py -v --live
```

### Selective Testing

```bash
# Run only unit tests
./tests/run_tests.sh --unit

# Run only integration tests
./tests/run_tests.sh --integration

# Run specific test class
pytest tests/test_avatar_looks_system.py::TestLookDefinitions -v

# Run specific test
pytest tests/test_avatar_looks_system.py::TestLookDefinitions::test_all_10_looks_are_defined -v
```

### With Coverage

```bash
# Generate coverage report
./tests/run_tests.sh --coverage

# View report in browser
open htmlcov/index.html
```

## Environment Variables

### Required for Live Testing

| Variable | Description |
|----------|-------------|
| `HEYGEN_API_KEY` | HeyGen API key for avatar generation |
| `HEYGEN_PHOTO_AVATAR_GROUP_ID` | Photo avatar group ID |
| `SUPABASE_URL` | Supabase database URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `HEYGEN_LOOK_POLL_TIMEOUT` | 300 | Timeout for polling look status (seconds) |
| `HEYGEN_LOOKS_TABLE` | avatar_looks | Database table name |
| `TEST_DRY_RUN` | true | Enable dry-run mode |
| `TEST_VERBOSE` | false | Enable verbose logging |

## Sample Test Output

### Successful Run

```
================================================================
   Avatar Looks System - Test Suite Runner
================================================================

Checking environment...
  Found virtual environment
  Python: Python 3.11.0
  Pytest: 7.4.0

Dry-run mode - using mocked API responses

Running tests...
----------------------------------------------------------------

tests/test_avatar_looks_system.py::TestLookDefinitions::test_all_10_looks_are_defined PASSED
tests/test_avatar_looks_system.py::TestLookDefinitions::test_each_look_has_required_fields PASSED
tests/test_avatar_looks_system.py::TestLookDefinitions::test_look_prompts_are_sufficiently_detailed PASSED
tests/test_avatar_looks_system.py::TestContentTypeDetection::test_detect_workout_content PASSED
tests/test_avatar_looks_system.py::TestContentTypeDetection::test_detect_professional_content PASSED
tests/test_avatar_looks_system.py::TestIntegrationFlow::test_full_look_generation_flow_mocked PASSED
...

================================================================
   Test Results Summary
================================================================

  Status:    PASSED
  Duration:  12 seconds
  Mode:      Dry-run

All tests passed! Ready for deployment.

Note: Tests ran in dry-run mode. For full validation before
production deployment, run with --live flag:

  ./tests/run_tests.sh --live

================================================================
```

## Deployment Checklist

Before deploying to Railway production, verify:

### Environment Variables
- [ ] HEYGEN_API_KEY is set
- [ ] HEYGEN_PHOTO_AVATAR_GROUP_ID is set
- [ ] SUPABASE_URL is set
- [ ] SUPABASE_ANON_KEY is set

### Database Schema
- [ ] avatar_looks table exists
- [ ] avatar_looks has required columns (look_id, photo_avatar_id, etc.)
- [ ] social_posts table exists

### API Connectivity
- [ ] HeyGen API authentication successful
- [ ] Supabase connection successful

### Look Definitions
- [ ] All 10 look definitions are valid
- [ ] Each look has required fields
- [ ] Look prompts are not empty

### Content Mapping
- [ ] Content type detection works
- [ ] Look selection returns valid LookInfo
- [ ] Avatar selection returns valid IDs

### Scheduler Integration
- [ ] Weekly avatar job is registered
- [ ] Theme rotation logic works
- [ ] Job can be triggered manually

### Backward Compatibility
- [ ] Existing video generation still works
- [ ] Avatar mapping returns valid IDs
- [ ] No breaking changes to public APIs

## Troubleshooting

### Test Discovery Fails

Ensure PYTHONPATH includes the project root:
```bash
export PYTHONPATH=/path/to/refiloe-marketing:$PYTHONPATH
```

### Import Errors

Check that all required packages are installed:
```bash
pip install -r requirements.txt
pip install pytest pytest-cov
```

### Mock Errors

If mocks aren't working correctly, ensure you're using the correct Python path:
```bash
cd /path/to/refiloe-marketing
python3 -m pytest tests/test_avatar_looks_system.py -v
```

### Live Tests Timeout

Increase the poll timeout for live tests:
```bash
export HEYGEN_LOOK_POLL_TIMEOUT=600
./tests/run_tests.sh --live
```

## CI/CD Integration

### Railway Deployment Check

Add to your deployment pipeline:

```yaml
# railway.yaml or similar
build:
  - pip install -r requirements.txt
  - pip install pytest
  - pytest tests/test_avatar_looks_system.py -v --tb=short
```

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Test Avatar Looks System

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-cov
      - run: pytest tests/test_avatar_looks_system.py -v --tb=short
```

## Contributing

When adding new features to the avatar looks system:

1. Add corresponding tests to `test_avatar_looks_system.py`
2. Update the deployment checklist if needed
3. Run the full test suite before submitting
4. Ensure backward compatibility tests still pass
