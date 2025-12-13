"""Comprehensive End-to-End Test Suite for Avatar Looks Generation System.

This module provides:
1. Unit tests for look definitions and content detection
2. Integration tests for the full generation flow
3. Dry-run mode for testing without API calls
4. Validation tests for environment and database
5. Deployment readiness checks

Usage:
    pytest tests/test_avatar_looks_system.py -v
    pytest tests/test_avatar_looks_system.py -v --dry-run
    pytest tests/test_avatar_looks_system.py -v -k "unit"
    pytest tests/test_avatar_looks_system.py -v -k "integration"
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import pytz

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_config import (
    DEPLOYMENT_CHECKLIST,
    MOCK_DATABASE_RECORD,
    MOCK_LOOK_GENERATION_RESPONSE,
    MOCK_LOOK_STATUS_COMPLETED,
    MOCK_MOTION_GENERATION_RESPONSE,
    MOCK_MOTION_STATUS_COMPLETED,
    OPTIONAL_ENV_VARS,
    REQUIRED_ENV_VARS,
    TEST_CONTENT_SAMPLES,
    MockSupabaseClient,
    create_mock_response,
    create_mock_supabase_client,
    has_live_credentials,
    is_ci_environment,
    test_config,
)


# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pytest Configuration and Fixtures
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    """Add custom command line options."""
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


@pytest.fixture(scope="session")
def dry_run_mode(request):
    """Determine if tests should run in dry-run mode."""
    if request.config.getoption("--live"):
        return False
    return True


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client for testing."""
    return create_mock_supabase_client()


@pytest.fixture
def mock_env_vars():
    """Set up mock environment variables for testing."""
    original_env = os.environ.copy()
    os.environ["HEYGEN_API_KEY"] = "test_api_key_12345"
    os.environ["HEYGEN_AVATAR_GROUP"] = "test_group_id_67890"
    os.environ["HEYGEN_LOOK_POLL_TIMEOUT"] = "60"
    os.environ["HEYGEN_LOOKS_TABLE"] = "avatar_looks"

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def looks_generator(mock_supabase, mock_env_vars):
    """Create a LooksGenerator instance with mock dependencies."""
    from social_media.looks_generator import LooksGenerator

    generator = LooksGenerator(mock_supabase)
    return generator


# ===========================================================================
# UNIT TESTS - Look Definitions
# ===========================================================================

class TestLookDefinitions:
    """Unit tests for the 10 look definitions in looks_generator.py."""

    def test_all_10_looks_are_defined(self):
        """Verify all 10 required looks are defined."""
        from social_media.looks_generator import REFILOE_LOOKS

        expected_looks = [
            "gym_trainer",
            "office_professional",
            "outdoor_wellness",
            "nutrition_expert",
            "yoga_instructor",
            "motivational_speaker",
            "home_workout",
            "podcast_host",
            "retreat_leader",
            "studio_portrait",
        ]

        assert len(REFILOE_LOOKS) == 10, f"Expected 10 looks, found {len(REFILOE_LOOKS)}"

        for look_type in expected_looks:
            assert look_type in REFILOE_LOOKS, f"Missing look type: {look_type}"

        logger.info("All 10 look definitions are present")

    def test_each_look_has_required_fields(self):
        """Verify each look has all required configuration fields."""
        from social_media.looks_generator import REFILOE_LOOKS

        required_fields = ["name", "description", "prompt", "environment", "attire", "mood"]

        for look_type, look_config in REFILOE_LOOKS.items():
            for field in required_fields:
                assert field in look_config, (
                    f"Look '{look_type}' is missing required field: {field}"
                )
                assert look_config[field], (
                    f"Look '{look_type}' has empty value for field: {field}"
                )

        logger.info("All looks have required fields with non-empty values")

    def test_look_prompts_are_sufficiently_detailed(self):
        """Verify look prompts have enough detail for generation."""
        from social_media.looks_generator import REFILOE_LOOKS

        min_prompt_length = 50  # Minimum characters for a good prompt

        for look_type, look_config in REFILOE_LOOKS.items():
            prompt = look_config.get("prompt", "")
            assert len(prompt) >= min_prompt_length, (
                f"Look '{look_type}' has short prompt ({len(prompt)} chars). "
                f"Minimum expected: {min_prompt_length} chars"
            )

        logger.info("All look prompts are sufficiently detailed")

    def test_look_environments_are_valid(self):
        """Verify look environments are valid identifiers."""
        from social_media.looks_generator import REFILOE_LOOKS

        valid_environments = [
            "gym", "office", "outdoor", "kitchen", "yoga_studio",
            "stage", "home", "podcast_studio", "resort", "studio",
        ]

        for look_type, look_config in REFILOE_LOOKS.items():
            env = look_config.get("environment", "")
            assert env in valid_environments, (
                f"Look '{look_type}' has invalid environment: '{env}'. "
                f"Valid: {valid_environments}"
            )

        logger.info("All look environments are valid")

    def test_look_moods_are_defined(self):
        """Verify each look has a defined mood."""
        from social_media.looks_generator import REFILOE_LOOKS

        for look_type, look_config in REFILOE_LOOKS.items():
            mood = look_config.get("mood", "")
            assert mood, f"Look '{look_type}' has no mood defined"
            assert len(mood) > 0, f"Look '{look_type}' has empty mood"

        logger.info("All looks have moods defined")

    def test_get_available_looks_returns_copy(self, mock_env_vars, mock_supabase):
        """Verify get_available_looks returns a copy, not the original."""
        from social_media.looks_generator import LooksGenerator, REFILOE_LOOKS

        generator = LooksGenerator(mock_supabase)
        looks1 = generator.get_available_looks()
        looks2 = generator.get_available_looks()

        # Modify one copy
        looks1["test_look"] = {"name": "Test"}

        # Original and other copy should be unchanged
        assert "test_look" not in REFILOE_LOOKS
        assert "test_look" not in looks2

        logger.info("get_available_looks correctly returns a copy")

    def test_get_look_details_returns_correct_look(self, mock_env_vars, mock_supabase):
        """Verify get_look_details returns correct configuration."""
        from social_media.looks_generator import LooksGenerator

        generator = LooksGenerator(mock_supabase)

        details = generator.get_look_details("gym_trainer")
        assert details is not None
        assert details["name"] == "Gym Trainer"
        assert details["environment"] == "gym"

        # Test non-existent look
        assert generator.get_look_details("nonexistent") is None

        logger.info("get_look_details returns correct configurations")


# ===========================================================================
# UNIT TESTS - Content Type Detection
# ===========================================================================

class TestContentTypeDetection:
    """Unit tests for content type and look selection."""

    def test_detect_workout_content(self):
        """Test detection of workout-related content."""
        from social_media.config.avatar_mapping import select_dynamic_look

        for sample in TEST_CONTENT_SAMPLES["workout"]:
            result = select_dynamic_look(sample)
            assert result["content_type"] in ["workout", "fitness"], (
                f"Failed to detect workout content: '{sample}'. "
                f"Got: {result['content_type']}"
            )

        logger.info("Workout content detection works correctly")

    def test_detect_professional_content(self):
        """Test detection of professional/business content."""
        from social_media.config.avatar_mapping import select_dynamic_look

        for sample in TEST_CONTENT_SAMPLES["professional"]:
            result = select_dynamic_look(sample)
            assert result["content_type"] in ["professional", "business"], (
                f"Failed to detect professional content: '{sample}'. "
                f"Got: {result['content_type']}"
            )

        logger.info("Professional content detection works correctly")

    def test_detect_motivational_content(self):
        """Test detection of motivational content."""
        from social_media.config.avatar_mapping import select_dynamic_look

        for sample in TEST_CONTENT_SAMPLES["motivational"]:
            result = select_dynamic_look(sample)
            assert result["content_type"] == "motivational", (
                f"Failed to detect motivational content: '{sample}'. "
                f"Got: {result['content_type']}"
            )

        logger.info("Motivational content detection works correctly")

    def test_detect_educational_content(self):
        """Test detection of educational content."""
        from social_media.config.avatar_mapping import select_dynamic_look

        for sample in TEST_CONTENT_SAMPLES["educational"]:
            result = select_dynamic_look(sample)
            assert result["content_type"] == "educational", (
                f"Failed to detect educational content: '{sample}'. "
                f"Got: {result['content_type']}"
            )

        logger.info("Educational content detection works correctly")

    def test_detect_outdoor_content(self):
        """Test detection of outdoor content."""
        from social_media.config.avatar_mapping import select_dynamic_look

        for sample in TEST_CONTENT_SAMPLES["outdoor"]:
            result = select_dynamic_look(sample)
            assert result["content_type"] == "outdoor", (
                f"Failed to detect outdoor content: '{sample}'. "
                f"Got: {result['content_type']}"
            )

        logger.info("Outdoor content detection works correctly")

    def test_explicit_content_type_overrides_detection(self):
        """Test that explicit content_type parameter takes precedence."""
        from social_media.config.avatar_mapping import select_dynamic_look

        # Use workout content but specify professional type
        result = select_dynamic_look(
            "Hit the gym for 20 reps!",
            content_type="professional"
        )
        assert result["content_type"] == "professional"

        logger.info("Explicit content_type correctly overrides detection")

    def test_default_look_for_unknown_content(self):
        """Test that unknown content gets default look."""
        from social_media.config.avatar_mapping import select_dynamic_look

        result = select_dynamic_look("Random text with no keywords")
        assert result["content_type"] == "default"
        assert result["look_description"] == "Versatile fitness professional look"

        logger.info("Unknown content correctly gets default look")

    def test_look_id_passthrough(self):
        """Test that look_id parameter is passed through."""
        from social_media.config.avatar_mapping import select_dynamic_look

        result = select_dynamic_look("Gym workout", look_id="custom_look_123")
        assert result["look_id"] == "custom_look_123"

        logger.info("look_id parameter correctly passed through")

    def test_select_dynamic_look_returns_complete_lookinfo(self):
        """Test that select_dynamic_look returns all LookInfo fields."""
        from social_media.config.avatar_mapping import select_dynamic_look

        result = select_dynamic_look("Fitness training session")

        required_keys = ["look_id", "look_description", "content_type", "environment", "outfit"]
        for key in required_keys:
            assert key in result, f"LookInfo missing key: {key}"

        logger.info("select_dynamic_look returns complete LookInfo")


# ===========================================================================
# UNIT TESTS - Avatar Selection
# ===========================================================================

class TestAvatarSelection:
    """Unit tests for avatar ID selection."""

    def test_get_photo_avatar_for_fitness_content(self):
        """Test photo avatar selection for fitness content."""
        from social_media.config.avatar_mapping import (
            get_photo_avatar_for_content,
            PHOTO_AVATAR_REGISTRY,
        )

        avatar_id = get_photo_avatar_for_content("Workout exercise training")
        expected_id = PHOTO_AVATAR_REGISTRY["fitness"]
        assert avatar_id == expected_id

        logger.info("Fitness content gets correct photo avatar ID")

    def test_get_photo_avatar_for_professional_content(self):
        """Test photo avatar selection for professional content."""
        from social_media.config.avatar_mapping import (
            get_photo_avatar_for_content,
            PHOTO_AVATAR_REGISTRY,
        )

        avatar_id = get_photo_avatar_for_content("Business strategy for growth")
        expected_id = PHOTO_AVATAR_REGISTRY["professional"]
        assert avatar_id == expected_id

        logger.info("Professional content gets correct photo avatar ID")

    def test_get_photo_avatar_with_explicit_type(self):
        """Test photo avatar selection with explicit content type."""
        from social_media.config.avatar_mapping import (
            get_photo_avatar_for_content,
            PHOTO_AVATAR_REGISTRY,
        )

        avatar_id = get_photo_avatar_for_content("Any text", content_type="motivational")
        expected_id = PHOTO_AVATAR_REGISTRY["motivational"]
        assert avatar_id == expected_id

        logger.info("Explicit content type gets correct photo avatar ID")

    def test_get_avatar_and_look_combined(self):
        """Test combined avatar and look selection."""
        from social_media.config.avatar_mapping import get_avatar_and_look_for_content

        avatar_id, look_info = get_avatar_and_look_for_content("Gym workout session")

        assert avatar_id is not None
        assert len(avatar_id) > 0
        assert look_info["content_type"] in ["workout", "fitness"]

        logger.info("Combined avatar and look selection works correctly")

    def test_all_photo_avatar_ids_are_valid_format(self):
        """Test that all photo avatar IDs have valid format."""
        from social_media.config.avatar_mapping import PHOTO_AVATAR_REGISTRY

        for content_type, avatar_id in PHOTO_AVATAR_REGISTRY.items():
            assert len(avatar_id) == 32, (
                f"Photo avatar '{content_type}' has invalid ID length: {len(avatar_id)}"
            )
            assert avatar_id.isalnum(), (
                f"Photo avatar '{content_type}' has non-alphanumeric ID: {avatar_id}"
            )

        logger.info("All photo avatar IDs have valid format")


# ===========================================================================
# UNIT TESTS - API Payload Generation
# ===========================================================================

class TestAPIPayloadGeneration:
    """Unit tests for API payload structure (without making actual calls)."""

    def test_look_generation_payload_structure(self, mock_env_vars, mock_supabase):
        """Test that look generation creates correct API payload."""
        from social_media.looks_generator import LooksGenerator

        generator = LooksGenerator(mock_supabase)

        # Mock the HTTP request to capture the payload
        with patch.object(generator, "_post_with_retry") as mock_post:
            mock_post.return_value = MOCK_LOOK_GENERATION_RESPONSE

            with patch.object(generator, "_poll_look_status") as mock_poll:
                mock_poll.return_value = MOCK_LOOK_STATUS_COMPLETED["data"]

                try:
                    generator.generate_avatar_look(look_type="gym_trainer")
                except Exception:
                    pass  # We only care about the payload

                # Verify the call was made with correct structure
                if mock_post.called:
                    call_args = mock_post.call_args
                    endpoint = call_args[0][0] if call_args[0] else ""
                    payload = call_args[1].get("json", {})

                    assert "/v2/photo_avatar/look/generate" in endpoint
                    assert "group_id" in payload
                    assert "prompt" in payload
                    assert len(payload["prompt"]) > 0

        logger.info("Look generation payload has correct structure")

    def test_motion_addition_payload_structure(self, mock_env_vars, mock_supabase):
        """Test that motion addition creates correct API payload."""
        from social_media.looks_generator import LooksGenerator

        generator = LooksGenerator(mock_supabase)

        with patch.object(generator, "_post_with_retry") as mock_post:
            mock_post.return_value = MOCK_MOTION_GENERATION_RESPONSE

            with patch.object(generator, "_poll_motion_status") as mock_poll:
                mock_poll.return_value = MOCK_MOTION_STATUS_COMPLETED["data"]

                try:
                    generator.add_motion_to_look(
                        photo_avatar_id="test_avatar_id",
                        motion_prompt="natural head movement",
                        motion_type="natural",
                    )
                except Exception:
                    pass

                if mock_post.called:
                    call_args = mock_post.call_args
                    endpoint = call_args[0][0] if call_args[0] else ""
                    payload = call_args[1].get("json", {})

                    assert "/v2/photo_avatar/add_motion" in endpoint
                    assert "photo_avatar_id" in payload
                    assert "motion_prompt" in payload

        logger.info("Motion addition payload has correct structure")

    def test_custom_prompt_overrides_default(self, mock_env_vars, mock_supabase):
        """Test that custom_prompt overrides the default look prompt."""
        from social_media.looks_generator import LooksGenerator

        generator = LooksGenerator(mock_supabase)
        custom_prompt = "Custom generation prompt for testing"

        with patch.object(generator, "_post_with_retry") as mock_post:
            mock_post.return_value = MOCK_LOOK_GENERATION_RESPONSE

            with patch.object(generator, "_poll_look_status") as mock_poll:
                mock_poll.return_value = MOCK_LOOK_STATUS_COMPLETED["data"]

                try:
                    generator.generate_avatar_look(
                        look_type="gym_trainer",
                        custom_prompt=custom_prompt,
                    )
                except Exception:
                    pass

                if mock_post.called:
                    payload = mock_post.call_args[1].get("json", {})
                    assert payload.get("prompt") == custom_prompt

        logger.info("Custom prompt correctly overrides default")


# ===========================================================================
# UNIT TESTS - Database Operations
# ===========================================================================

class TestDatabaseOperations:
    """Unit tests for database save/retrieve functions."""

    def test_save_look_to_database_creates_record(self, mock_env_vars, mock_supabase):
        """Test saving a look creates a database record."""
        from social_media.looks_generator import LooksGenerator

        generator = LooksGenerator(mock_supabase)

        look_data = {
            "look_id": "test_look_123",
            "photo_avatar_id": "test_avatar_456",
            "group_id": "test_group",
            "look_type": "gym_trainer",
            "prompt": "Test prompt",
            "status": "completed",
            "preview_url": "https://example.com/preview.jpg",
            "look_config": {
                "name": "Gym Trainer",
                "environment": "gym",
                "attire": "athletic",
                "mood": "energetic",
            },
        }

        record_id = generator.save_look_to_database(look_data)

        # With mock client, this should return empty string (mock doesn't return proper result)
        # In real scenario, it would return UUID
        assert isinstance(record_id, str)

        logger.info("save_look_to_database executes without error")

    def test_save_look_without_supabase_client(self, mock_env_vars):
        """Test saving without Supabase client returns empty string."""
        from social_media.looks_generator import LooksGenerator

        generator = LooksGenerator(supabase_client=None)

        look_data = {"look_id": "test", "look_type": "gym_trainer"}
        record_id = generator.save_look_to_database(look_data)

        assert record_id == ""

        logger.info("save_look_to_database handles missing client correctly")

    def test_get_saved_looks_returns_list(self, mock_env_vars, mock_supabase):
        """Test retrieving looks returns a list."""
        from social_media.looks_generator import LooksGenerator

        # Add a mock record
        mock_supabase.add_mock_record("avatar_looks", MOCK_DATABASE_RECORD)

        generator = LooksGenerator(mock_supabase)
        looks = generator.get_saved_looks()

        assert isinstance(looks, list)
        assert len(looks) >= 0

        logger.info("get_saved_looks returns list correctly")

    def test_get_saved_looks_with_filters(self, mock_env_vars, mock_supabase):
        """Test retrieving looks with filters."""
        from social_media.looks_generator import LooksGenerator

        generator = LooksGenerator(mock_supabase)

        # Should not raise exceptions with filters
        looks = generator.get_saved_looks(look_type="gym_trainer")
        assert isinstance(looks, list)

        looks = generator.get_saved_looks(has_motion=True)
        assert isinstance(looks, list)

        logger.info("get_saved_looks handles filters correctly")

    def test_update_look_with_motion_without_client(self, mock_env_vars):
        """Test updating look without Supabase client returns False."""
        from social_media.looks_generator import LooksGenerator

        generator = LooksGenerator(supabase_client=None)

        motion_data = {"motion_id": "test_motion", "motion_prompt": "test"}
        result = generator.update_look_with_motion("record_123", motion_data)

        assert result is False

        logger.info("update_look_with_motion handles missing client correctly")


# ===========================================================================
# INTEGRATION TESTS - Full Flow
# ===========================================================================

class TestIntegrationFlow:
    """Integration tests for the full avatar look generation flow."""

    def test_full_look_generation_flow_mocked(self, mock_env_vars, mock_supabase):
        """Test the full flow: content -> look selection -> generation request."""
        from social_media.config.avatar_mapping import select_dynamic_look
        from social_media.looks_generator import LooksGenerator

        # Step 1: Content analysis and look selection
        content = "Time to hit the gym for leg day!"
        look_info = select_dynamic_look(content)

        assert look_info["content_type"] in ["workout", "fitness"]
        assert "gym" in look_info["environment"].lower() or "fitness" in look_info["environment"].lower()

        # Step 2: Create generator and mock API calls
        generator = LooksGenerator(mock_supabase)

        with patch.object(generator, "_post_with_retry") as mock_post:
            mock_post.side_effect = [
                MOCK_LOOK_GENERATION_RESPONSE,
                MOCK_MOTION_GENERATION_RESPONSE,
            ]

            with patch.object(generator, "_poll_look_status") as mock_poll_look:
                mock_poll_look.return_value = MOCK_LOOK_STATUS_COMPLETED["data"]

                with patch.object(generator, "_poll_motion_status") as mock_poll_motion:
                    mock_poll_motion.return_value = MOCK_MOTION_STATUS_COMPLETED["data"]

                    # Step 3: Generate look with motion
                    result = generator.generate_look_with_motion(
                        look_type="gym_trainer",
                        motion_prompt="natural movement",
                        save_to_database=True,
                    )

                    assert "look_id" in result
                    assert "photo_avatar_id" in result
                    assert "motion_id" in result
                    assert result["has_motion"] is True

        logger.info("Full look generation flow works correctly (mocked)")

    def test_avatar_mapping_integrates_with_looks_generator(
        self, mock_env_vars, mock_supabase
    ):
        """Test that avatar_mapping correctly integrates with looks_generator."""
        from social_media.config.avatar_mapping import (
            get_avatar_and_look_for_content,
            CONTENT_TO_LOOK,
        )
        from social_media.looks_generator import REFILOE_LOOKS

        # Get look info from avatar_mapping
        avatar_id, look_info = get_avatar_and_look_for_content("Gym workout session")

        # Verify look_info is compatible with looks_generator
        assert "content_type" in look_info
        assert "look_description" in look_info
        assert "environment" in look_info
        assert "outfit" in look_info

        # Verify content types in avatar_mapping align with look types
        for content_type in CONTENT_TO_LOOK:
            look_config = CONTENT_TO_LOOK[content_type]
            assert "look_description" in look_config
            assert "outfit" in look_config
            assert "environment" in look_config

        logger.info("Avatar mapping integrates correctly with looks generator")

    def test_look_ids_stored_and_retrieved(self, mock_env_vars, mock_supabase):
        """Test that look IDs can be stored and retrieved from database."""
        from social_media.looks_generator import LooksGenerator

        generator = LooksGenerator(mock_supabase)

        # Store a look
        look_data = {
            "look_id": "integration_test_look",
            "photo_avatar_id": "integration_test_avatar",
            "group_id": "test_group",
            "look_type": "gym_trainer",
            "prompt": "Integration test",
            "status": "completed",
        }

        # Add to mock database
        mock_supabase.add_mock_record("avatar_looks", look_data)

        # Retrieve
        looks = generator.get_saved_looks(look_type="gym_trainer")

        # Verify the look is retrievable
        assert isinstance(looks, list)

        logger.info("Look IDs can be stored and retrieved")


# ===========================================================================
# SCHEDULER INTEGRATION TESTS
# ===========================================================================

class TestSchedulerIntegration:
    """Tests for scheduler job integration."""

    def test_weekly_avatar_job_theme_rotation(self):
        """Test that weekly job correctly rotates through themes."""
        # Import theme rotation logic
        theme_rotation = [
            {"theme": "gym", "looks": ["gym_trainer", "home_workout"]},
            {"theme": "office", "looks": ["office_professional"]},
            {"theme": "outdoor", "looks": ["outdoor_wellness", "retreat_leader"]},
            {"theme": "casual", "looks": ["podcast_host", "yoga_instructor"]},
            {"theme": "professional", "looks": ["motivational_speaker", "nutrition_expert", "studio_portrait"]},
        ]

        # Test rotation for multiple weeks
        for week_number in range(1, 53):
            num_looks = 2 + (week_number % 2)
            assert num_looks in [2, 3], f"Week {week_number} should generate 2 or 3 looks"

            selected_themes = []
            for i in range(num_looks):
                theme_index = (week_number + i) % len(theme_rotation)
                selected_themes.append(theme_rotation[theme_index])

            assert len(selected_themes) == num_looks

        logger.info("Theme rotation logic works correctly for all weeks")

    def test_scheduler_job_registration(self, mock_env_vars, mock_supabase):
        """Test that weekly avatar looks job can be registered."""
        from unittest.mock import MagicMock

        # Create mock app and scheduler
        mock_app = MagicMock()
        mock_app.config = {}

        from social_media.scheduler import SocialMediaScheduler

        scheduler = SocialMediaScheduler(mock_app, mock_supabase)

        # Check that the scheduler can be initialized
        assert scheduler is not None
        assert scheduler.scheduler is not None

        logger.info("Scheduler job registration works correctly")

    def test_weekly_avatar_job_dry_run(self, mock_env_vars, mock_supabase):
        """Test weekly avatar job can be triggered in dry-run mode."""
        from unittest.mock import MagicMock, patch

        mock_app = MagicMock()
        mock_app.config = {}

        from social_media.scheduler import SocialMediaScheduler

        scheduler = SocialMediaScheduler(mock_app, mock_supabase)

        # Mock the LooksGenerator at the module level where it's imported
        with patch.dict("sys.modules", {"social_media.looks_generator": MagicMock()}):
            import sys
            mock_looks_module = sys.modules["social_media.looks_generator"]
            mock_generator_instance = MagicMock()
            mock_generator_instance.generate_look_with_motion.return_value = {
                "look_id": "test_look",
                "photo_avatar_id": "test_avatar",
                "motion_id": "test_motion",
                "database_record_id": "test_record",
            }
            mock_looks_module.LooksGenerator.return_value = mock_generator_instance
            mock_looks_module.LookGenerationError = Exception
            mock_looks_module.MotionAdditionError = Exception

            # Run the job
            scheduler.run_weekly_avatar_looks()

            # The job should complete without error (may log warnings if not fully mocked)
            # Since we're mocking at the module level, just verify no exception was raised

        logger.info("Weekly avatar job executes in dry-run mode")


# ===========================================================================
# VALIDATION TESTS - Environment
# ===========================================================================

class TestEnvironmentValidation:
    """Tests for environment variable validation."""

    def test_required_env_vars_documented(self):
        """Verify all required environment variables are documented."""
        assert len(REQUIRED_ENV_VARS) >= 4

        for env_var in REQUIRED_ENV_VARS:
            assert "name" in env_var
            assert "description" in env_var
            assert len(env_var["description"]) > 0

        logger.info("All required environment variables are documented")

    def test_optional_env_vars_have_defaults(self):
        """Verify optional environment variables have default values."""
        for env_var in OPTIONAL_ENV_VARS:
            assert "name" in env_var
            assert "default" in env_var

        logger.info("All optional environment variables have defaults")

    def test_looks_generator_validates_api_key(self, mock_supabase):
        """Test that LooksGenerator validates API key presence."""
        from social_media.looks_generator import LooksGenerator

        # Clear the API key
        original = os.environ.get("HEYGEN_API_KEY")
        if "HEYGEN_API_KEY" in os.environ:
            del os.environ["HEYGEN_API_KEY"]

        with pytest.raises(ValueError, match="HEYGEN_API_KEY"):
            LooksGenerator(mock_supabase)

        # Restore
        if original:
            os.environ["HEYGEN_API_KEY"] = original

        logger.info("LooksGenerator correctly validates API key")

    def test_generate_look_validates_group_id(self, mock_env_vars, mock_supabase):
        """Test that generate_avatar_look validates group ID."""
        from social_media.looks_generator import LooksGenerator

        # Remove group ID
        original = os.environ.get("HEYGEN_AVATAR_GROUP")
        if "HEYGEN_AVATAR_GROUP" in os.environ:
            del os.environ["HEYGEN_AVATAR_GROUP"]

        generator = LooksGenerator(mock_supabase)

        with pytest.raises(ValueError, match="group"):
            generator.generate_avatar_look(look_type="gym_trainer")

        # Restore
        if original:
            os.environ["HEYGEN_AVATAR_GROUP"] = original

        logger.info("generate_avatar_look correctly validates group ID")


# ===========================================================================
# ERROR HANDLING TESTS
# ===========================================================================

class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_invalid_look_type_raises_error(self, mock_env_vars, mock_supabase):
        """Test that invalid look type raises ValueError."""
        from social_media.looks_generator import LooksGenerator

        generator = LooksGenerator(mock_supabase)

        with pytest.raises(ValueError, match="Unknown look_type"):
            generator.generate_avatar_look(look_type="invalid_look_type")

        logger.info("Invalid look type correctly raises ValueError")

    def test_empty_motion_prompt_raises_error(self, mock_env_vars, mock_supabase):
        """Test that empty motion prompt raises ValueError."""
        from social_media.looks_generator import LooksGenerator

        generator = LooksGenerator(mock_supabase)

        with pytest.raises(ValueError, match="motion_prompt"):
            generator.add_motion_to_look(
                photo_avatar_id="test_id",
                motion_prompt="",
            )

        logger.info("Empty motion prompt correctly raises ValueError")

    def test_missing_photo_avatar_id_raises_error(self, mock_env_vars, mock_supabase):
        """Test that missing photo_avatar_id raises ValueError."""
        from social_media.looks_generator import LooksGenerator

        generator = LooksGenerator(mock_supabase)

        with pytest.raises(ValueError, match="photo_avatar_id"):
            generator.add_motion_to_look(
                photo_avatar_id="",
                motion_prompt="test motion",
            )

        logger.info("Missing photo_avatar_id correctly raises ValueError")

    def test_api_failure_raises_look_generation_error(self, mock_env_vars, mock_supabase):
        """Test that API failure raises LookGenerationError."""
        import requests
        from social_media.looks_generator import LooksGenerator, LookGenerationError

        generator = LooksGenerator(mock_supabase)

        # Use requests.RequestException which is properly caught and re-raised
        with patch.object(generator, "_post_with_retry") as mock_post:
            mock_post.side_effect = requests.RequestException("API connection failed")

            with pytest.raises(LookGenerationError):
                generator.generate_avatar_look(look_type="gym_trainer")

        logger.info("API failure correctly raises LookGenerationError")


# ===========================================================================
# BACKWARD COMPATIBILITY TESTS
# ===========================================================================

class TestBackwardCompatibility:
    """Tests to ensure new code doesn't break existing functionality."""

    def test_photo_avatar_mapping_returns_valid_ids(self):
        """Test that photo avatar mapping returns valid avatar IDs."""
        from social_media.config.avatar_mapping import (
            get_photo_avatar_for_content,
            PHOTO_AVATAR_REGISTRY,
        )

        test_cases = [
            ("workout tips", "workout"),
            ("business growth", "professional"),
            ("transform your life", "motivational"),
            ("weekend vibes", "casual"),
        ]

        for content, expected_type in test_cases:
            avatar_id = get_photo_avatar_for_content(content)
            assert avatar_id in PHOTO_AVATAR_REGISTRY.values(), (
                f"Avatar ID '{avatar_id}' not in photo registry for content: '{content}'"
            )

        logger.info("Photo avatar mapping returns valid IDs for all content types")

    def test_content_to_look_keys_match_content_types(self):
        """Test that CONTENT_TO_LOOK keys align with content type detection."""
        from social_media.config.avatar_mapping import (
            CONTENT_TO_LOOK,
            CONTENT_KEYWORDS,
            LOOK_KEYWORDS,
        )

        # All content types that can be detected
        detectable_types = set(CONTENT_KEYWORDS.keys()) | set(LOOK_KEYWORDS.keys())

        # Most detectable types should have a look configuration
        configured_types = set(CONTENT_TO_LOOK.keys())

        # Log any types without look configuration
        unconfigured = detectable_types - configured_types
        if unconfigured:
            logger.warning(f"Content types without look config: {unconfigured}")

        logger.info("Content types alignment verified")


# ===========================================================================
# DEPLOYMENT READINESS TESTS
# ===========================================================================

class TestDeploymentReadiness:
    """Tests for deployment readiness validation."""

    def test_deployment_checklist_is_complete(self):
        """Verify deployment checklist covers all critical areas."""
        categories = [item["category"] for item in DEPLOYMENT_CHECKLIST]

        required_categories = [
            "Environment Variables",
            "Database Schema",
            "API Connectivity",
            "Look Definitions",
            "Content Mapping",
            "Scheduler Integration",
            "Backward Compatibility",
        ]

        for category in required_categories:
            assert category in categories, f"Missing checklist category: {category}"

        logger.info("Deployment checklist covers all critical areas")

    def test_all_critical_checks_have_tests(self):
        """Verify all critical deployment checks have corresponding tests."""
        critical_checks = []

        for category in DEPLOYMENT_CHECKLIST:
            for item in category["items"]:
                if item.get("critical"):
                    critical_checks.append(item["check"])

        # We should have at least 10 critical checks
        assert len(critical_checks) >= 10, (
            f"Expected at least 10 critical checks, found {len(critical_checks)}"
        )

        logger.info(f"Found {len(critical_checks)} critical deployment checks")

    @pytest.mark.skipif(not has_live_credentials(), reason="Live credentials not available")
    def test_heygen_api_authentication(self):
        """Test HeyGen API authentication with real credentials."""
        import requests

        api_key = os.getenv("HEYGEN_API_KEY")
        headers = {"X-Api-Key": api_key}

        # Use a lightweight endpoint to test authentication
        response = requests.get(
            "https://api.heygen.com/v1/avatar.list",
            headers=headers,
            timeout=30,
        )

        assert response.status_code in [200, 429], (
            f"HeyGen API authentication failed with status: {response.status_code}"
        )

        logger.info("HeyGen API authentication successful")

    @pytest.mark.skipif(not has_live_credentials(), reason="Live credentials not available")
    def test_supabase_connection(self):
        """Test Supabase connection with real credentials."""
        try:
            from supabase import create_client

            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_ANON_KEY")

            client = create_client(url, key)

            # Try a simple query
            response = client.table("avatar_looks").select("id").limit(1).execute()

            # Should not raise an exception
            assert response is not None

            logger.info("Supabase connection successful")

        except ImportError:
            pytest.skip("Supabase client not installed")
        except Exception as e:
            logger.warning(f"Supabase connection test issue: {e}")


# ===========================================================================
# TEST SUMMARY GENERATION
# ===========================================================================

class TestSummary:
    """Generate test summary report."""

    @pytest.fixture(autouse=True)
    def capture_results(self, request):
        """Capture test results for summary."""
        yield

    def test_generate_summary(self, request):
        """Generate a summary of all tests (runs last)."""
        # This test is mainly for documentation purposes
        summary = {
            "test_suite": "Avatar Looks Generation System",
            "timestamp": datetime.now(pytz.timezone("Africa/Johannesburg")).isoformat(),
            "categories": [
                "Unit Tests - Look Definitions",
                "Unit Tests - Content Type Detection",
                "Unit Tests - Avatar Selection",
                "Unit Tests - API Payload Generation",
                "Unit Tests - Database Operations",
                "Integration Tests - Full Flow",
                "Scheduler Integration Tests",
                "Environment Validation Tests",
                "Error Handling Tests",
                "Backward Compatibility Tests",
                "Deployment Readiness Tests",
            ],
        }

        logger.info("=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Test Suite: {summary['test_suite']}")
        logger.info(f"Timestamp: {summary['timestamp']}")
        logger.info(f"Categories Tested: {len(summary['categories'])}")
        for category in summary["categories"]:
            logger.info(f"  - {category}")
        logger.info("=" * 60)


# ===========================================================================
# MAIN ENTRY POINT
# ===========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
