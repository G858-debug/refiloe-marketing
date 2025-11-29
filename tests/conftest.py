"""Pytest configuration and shared fixtures for the avatar looks test suite.

This module provides:
- Command line options for test modes
- Shared fixtures for mocking
- Test collection customization
"""

from __future__ import annotations

import os
import sys
from typing import Generator

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_addoption(parser):
    """Add custom command line options for the test suite."""
    parser.addoption(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run tests in dry-run mode (no real API calls)",
    )
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run tests with live API calls (requires credentials)",
    )


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "live: mark test to run only with live API credentials"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on command line options."""
    if config.getoption("--live"):
        # Running in live mode - don't skip live tests
        return

    # Skip tests marked with 'live' when not in live mode
    skip_live = pytest.mark.skip(reason="Need --live option to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(scope="session")
def is_live_mode(request) -> bool:
    """Determine if tests are running in live mode."""
    return request.config.getoption("--live")


@pytest.fixture(scope="session")
def project_root() -> str:
    """Return the project root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def mock_env_complete() -> Generator[dict, None, None]:
    """Set up complete mock environment variables for testing."""
    original_env = os.environ.copy()

    test_env = {
        "HEYGEN_API_KEY": "test_api_key_12345",
        "HEYGEN_AVATAR_GROUP": "test_group_id_67890",
        "HEYGEN_LOOK_POLL_TIMEOUT": "60",
        "HEYGEN_LOOKS_TABLE": "avatar_looks_test",
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_ANON_KEY": "test_anon_key",
    }

    for key, value in test_env.items():
        os.environ[key] = value

    yield test_env

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def sample_look_data() -> dict:
    """Provide sample look data for testing."""
    return {
        "look_id": "test_look_123",
        "photo_avatar_id": "test_avatar_456",
        "group_id": "test_group",
        "look_type": "gym_trainer",
        "prompt": "Test prompt for gym trainer look",
        "status": "completed",
        "preview_url": "https://example.com/preview.jpg",
        "look_config": {
            "name": "Gym Trainer",
            "environment": "gym",
            "attire": "athletic",
            "mood": "energetic",
        },
        "has_motion": False,
    }


@pytest.fixture
def sample_motion_data() -> dict:
    """Provide sample motion data for testing."""
    return {
        "motion_id": "test_motion_789",
        "photo_avatar_id": "test_avatar_456",
        "status": "completed",
        "motion_prompt": "natural head movement and subtle expressions",
        "motion_type": "natural",
        "preview_url": "https://example.com/motion.mp4",
    }


# Test result collection for summary
_test_results = []


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Collect test results for summary reporting."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        _test_results.append({
            "name": item.name,
            "nodeid": item.nodeid,
            "outcome": report.outcome,
            "duration": report.duration,
        })


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print custom summary at the end of test run."""
    terminalreporter.write_sep("=", "Avatar Looks System Test Summary")

    passed = sum(1 for r in _test_results if r["outcome"] == "passed")
    failed = sum(1 for r in _test_results if r["outcome"] == "failed")
    skipped = sum(1 for r in _test_results if r["outcome"] == "skipped")
    total = len(_test_results)

    terminalreporter.write_line(f"Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")

    if exitstatus == 0:
        terminalreporter.write_line("")
        terminalreporter.write_line("All tests passed! Ready for deployment.", green=True)
    else:
        terminalreporter.write_line("")
        terminalreporter.write_line("Some tests failed. Please fix before deploying.", red=True)

    # Clear results for next run
    _test_results.clear()
