"""Test configuration for the avatar looks system test suite.

This module provides test configuration, mock data, and utilities for running
tests in different environments (local, CI/CD, dry-run mode).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Environment Detection
# ---------------------------------------------------------------------------

def is_ci_environment() -> bool:
    """Check if running in CI/CD environment."""
    ci_indicators = ["CI", "GITHUB_ACTIONS", "RAILWAY_ENVIRONMENT", "RAILWAY"]
    return any(os.getenv(indicator) for indicator in ci_indicators)


def has_live_credentials() -> bool:
    """Check if live API credentials are available."""
    return bool(
        os.getenv("HEYGEN_API_KEY")
        and os.getenv("HEYGEN_PHOTO_AVATAR_GROUP_ID")
        and os.getenv("SUPABASE_URL")
        and os.getenv("SUPABASE_ANON_KEY")
    )


# ---------------------------------------------------------------------------
# Test Configuration
# ---------------------------------------------------------------------------

@dataclass
class TestConfig:
    """Configuration class for test suite settings."""

    # Environment flags
    dry_run: bool = True
    skip_live_api: bool = True
    skip_database: bool = True
    verbose: bool = False

    # Timeouts (in seconds)
    api_timeout: int = 30
    poll_timeout: int = 60

    # Mock settings
    use_mock_responses: bool = True
    mock_generation_delay: float = 0.1

    # Test database settings (for integration tests)
    test_table_suffix: str = "_test"
    cleanup_after_tests: bool = True

    @classmethod
    def from_env(cls) -> "TestConfig":
        """Create configuration from environment variables."""
        return cls(
            dry_run=os.getenv("TEST_DRY_RUN", "true").lower() == "true",
            skip_live_api=os.getenv("TEST_SKIP_LIVE_API", "true").lower() == "true",
            skip_database=os.getenv("TEST_SKIP_DATABASE", "true").lower() == "true",
            verbose=os.getenv("TEST_VERBOSE", "false").lower() == "true",
            api_timeout=int(os.getenv("TEST_API_TIMEOUT", "30")),
            poll_timeout=int(os.getenv("TEST_POLL_TIMEOUT", "60")),
        )

    @classmethod
    def for_live_testing(cls) -> "TestConfig":
        """Create configuration for live API testing."""
        return cls(
            dry_run=False,
            skip_live_api=False,
            skip_database=False,
            use_mock_responses=False,
            verbose=True,
        )


# Global test configuration instance
test_config = TestConfig.from_env()


# ---------------------------------------------------------------------------
# Required Environment Variables
# ---------------------------------------------------------------------------

REQUIRED_ENV_VARS = [
    {
        "name": "HEYGEN_API_KEY",
        "description": "HeyGen API key for avatar generation",
        "required_for": ["live_api", "production"],
    },
    {
        "name": "HEYGEN_PHOTO_AVATAR_GROUP_ID",
        "description": "Photo avatar group ID for look generation",
        "required_for": ["live_api", "production"],
    },
    {
        "name": "SUPABASE_URL",
        "description": "Supabase database URL",
        "required_for": ["database", "production"],
    },
    {
        "name": "SUPABASE_ANON_KEY",
        "description": "Supabase anonymous key for authentication",
        "required_for": ["database", "production"],
    },
]

OPTIONAL_ENV_VARS = [
    {
        "name": "HEYGEN_LOOK_POLL_TIMEOUT",
        "description": "Timeout for polling look generation status (default: 300s)",
        "default": "300",
    },
    {
        "name": "HEYGEN_LOOKS_TABLE",
        "description": "Database table for avatar looks (default: avatar_looks)",
        "default": "avatar_looks",
    },
]


# ---------------------------------------------------------------------------
# Mock Data
# ---------------------------------------------------------------------------

MOCK_LOOK_GENERATION_RESPONSE = {
    "data": {
        "look_id": "mock_look_12345",
        "id": "mock_look_12345",
    }
}

MOCK_LOOK_STATUS_PENDING = {
    "data": {
        "look_id": "mock_look_12345",
        "status": "processing",
    }
}

MOCK_LOOK_STATUS_COMPLETED = {
    "data": {
        "look_id": "mock_look_12345",
        "status": "completed",
        "photo_avatar_id": "mock_avatar_67890",
        "preview_url": "https://example.com/preview/mock_look.jpg",
    }
}

MOCK_MOTION_GENERATION_RESPONSE = {
    "data": {
        "motion_id": "mock_motion_11111",
        "task_id": "mock_motion_11111",
    }
}

MOCK_MOTION_STATUS_COMPLETED = {
    "data": {
        "motion_id": "mock_motion_11111",
        "status": "completed",
        "preview_url": "https://example.com/preview/mock_motion.mp4",
    }
}

MOCK_DATABASE_RECORD = {
    "id": "test-uuid-12345",
    "look_id": "mock_look_12345",
    "photo_avatar_id": "mock_avatar_67890",
    "group_id": "test_group_id",
    "look_type": "gym_trainer",
    "prompt": "Test prompt",
    "status": "completed",
    "preview_url": "https://example.com/preview/mock_look.jpg",
    "look_config": {
        "name": "Gym Trainer",
        "environment": "gym",
        "attire": "athletic",
        "mood": "energetic",
    },
    "has_motion": True,
    "motion_id": "mock_motion_11111",
    "motion_prompt": "natural head movement",
    "motion_type": "natural",
    "created_at": "2025-11-28T10:00:00+02:00",
    "updated_at": "2025-11-28T10:00:00+02:00",
}


# ---------------------------------------------------------------------------
# Mock Supabase Client
# ---------------------------------------------------------------------------

class MockSupabaseResponse:
    """Mock response object for Supabase queries."""

    def __init__(self, data: Optional[List[Dict]] = None, count: int = 0):
        self.data = data or []
        self.count = count


class MockSupabaseQuery:
    """Mock Supabase query builder."""

    def __init__(self, table_name: str, data: Optional[List[Dict]] = None):
        self.table_name = table_name
        self._data = data or []
        self._filters: Dict[str, Any] = {}

    def select(self, *args, **kwargs) -> "MockSupabaseQuery":
        return self

    def insert(self, record: Dict) -> "MockSupabaseQuery":
        self._data.append(record)
        return self

    def update(self, data: Dict) -> "MockSupabaseQuery":
        return self

    def eq(self, field: str, value: Any) -> "MockSupabaseQuery":
        self._filters[field] = value
        return self

    def order(self, field: str, desc: bool = False) -> "MockSupabaseQuery":
        return self

    def limit(self, count: int) -> "MockSupabaseQuery":
        return self

    def single(self) -> "MockSupabaseQuery":
        return self

    def execute(self) -> MockSupabaseResponse:
        # Apply filters if any
        filtered_data = self._data
        if self._filters:
            for field, value in self._filters.items():
                filtered_data = [d for d in filtered_data if d.get(field) == value]
        return MockSupabaseResponse(data=filtered_data, count=len(filtered_data))


class MockSupabaseClient:
    """Mock Supabase client for testing without database access."""

    def __init__(self):
        self._tables: Dict[str, List[Dict]] = {
            "avatar_looks": [],
            "social_posts": [],
        }

    def table(self, table_name: str) -> MockSupabaseQuery:
        if table_name not in self._tables:
            self._tables[table_name] = []
        return MockSupabaseQuery(table_name, self._tables[table_name])

    def add_mock_record(self, table_name: str, record: Dict) -> None:
        """Add a mock record to a table for testing."""
        if table_name not in self._tables:
            self._tables[table_name] = []
        self._tables[table_name].append(record)

    def get_records(self, table_name: str) -> List[Dict]:
        """Get all records from a mock table."""
        return self._tables.get(table_name, [])

    def clear_table(self, table_name: str) -> None:
        """Clear all records from a mock table."""
        if table_name in self._tables:
            self._tables[table_name] = []


def create_mock_supabase_client() -> MockSupabaseClient:
    """Factory function to create a mock Supabase client."""
    return MockSupabaseClient()


# ---------------------------------------------------------------------------
# Mock HTTP Responses
# ---------------------------------------------------------------------------

class MockHTTPResponse:
    """Mock HTTP response for testing API calls."""

    def __init__(
        self,
        status_code: int = 200,
        json_data: Optional[Dict] = None,
        text: str = "",
    ):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self) -> Dict:
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            from requests.exceptions import HTTPError
            raise HTTPError(f"HTTP {self.status_code}")


def create_mock_response(
    endpoint: str,
    method: str = "POST",
    success: bool = True,
) -> MockHTTPResponse:
    """Create a mock HTTP response based on the endpoint."""

    if not success:
        return MockHTTPResponse(status_code=500, json_data={"error": "Mock error"})

    if "look/generate" in endpoint:
        return MockHTTPResponse(json_data=MOCK_LOOK_GENERATION_RESPONSE)

    if "look/" in endpoint and "status" in endpoint:
        return MockHTTPResponse(json_data=MOCK_LOOK_STATUS_COMPLETED)

    if "add_motion" in endpoint:
        return MockHTTPResponse(json_data=MOCK_MOTION_GENERATION_RESPONSE)

    if "motion/" in endpoint and "status" in endpoint:
        return MockHTTPResponse(json_data=MOCK_MOTION_STATUS_COMPLETED)

    return MockHTTPResponse(json_data={"data": {}})


# ---------------------------------------------------------------------------
# Test Content Samples
# ---------------------------------------------------------------------------

TEST_CONTENT_SAMPLES = {
    "workout": [
        "Hit the gym today! 20 reps of squats and deadlifts.",
        "Cardio session: 30 minutes HIIT followed by weights.",
        "Leg day at the gym - feeling the burn with those lifts!",
    ],
    "fitness": [
        "Master your form with these exercise tips.",
        "Training technique breakdown for better results.",
        "Proper squat form demonstration.",
    ],
    "professional": [
        "Business strategy for personal trainers.",
        "Revenue growth tips for your fitness business.",
        "Client acquisition and business growth strategies.",
    ],
    "motivational": [
        "Transform your life through fitness!",
        "Success stories: achieving your goals.",
        "Inspire change, achieve greatness.",
    ],
    "educational": [
        "Tips and tricks for meal prep.",
        "How to build a sustainable fitness routine.",
        "Guide to nutrition basics.",
    ],
    "casual": [
        "Happy Friday everyone! Weekend vibes.",
        "Relaxing after a great week.",
        "Fun weekend ahead - enjoy yourselves!",
    ],
    "outdoor": [
        "Outdoor bootcamp session in the park today!",
        "Trail running in nature - fresh air therapy.",
        "Sunshine bootcamp at the park this morning.",
    ],
    "default": [
        "New content coming soon!",
        "Stay tuned for updates.",
        "Hello everyone!",
    ],
}


# ---------------------------------------------------------------------------
# Deployment Readiness Checklist
# ---------------------------------------------------------------------------

DEPLOYMENT_CHECKLIST = [
    {
        "category": "Environment Variables",
        "items": [
            {"check": "HEYGEN_API_KEY is set", "critical": True},
            {"check": "HEYGEN_PHOTO_AVATAR_GROUP_ID is set", "critical": True},
            {"check": "SUPABASE_URL is set", "critical": True},
            {"check": "SUPABASE_ANON_KEY is set", "critical": True},
        ],
    },
    {
        "category": "Database Schema",
        "items": [
            {"check": "avatar_looks table exists", "critical": True},
            {"check": "avatar_looks has required columns", "critical": True},
            {"check": "social_posts table exists", "critical": False},
        ],
    },
    {
        "category": "API Connectivity",
        "items": [
            {"check": "HeyGen API authentication successful", "critical": True},
            {"check": "Supabase connection successful", "critical": True},
        ],
    },
    {
        "category": "Look Definitions",
        "items": [
            {"check": "All 10 look definitions are valid", "critical": True},
            {"check": "Each look has required fields", "critical": True},
            {"check": "Look prompts are not empty", "critical": True},
        ],
    },
    {
        "category": "Content Mapping",
        "items": [
            {"check": "Content type detection works", "critical": True},
            {"check": "Look selection returns valid LookInfo", "critical": True},
            {"check": "Avatar selection returns valid IDs", "critical": True},
        ],
    },
    {
        "category": "Scheduler Integration",
        "items": [
            {"check": "Weekly avatar job is registered", "critical": True},
            {"check": "Theme rotation logic works", "critical": True},
            {"check": "Job can be triggered manually", "critical": False},
        ],
    },
    {
        "category": "Backward Compatibility",
        "items": [
            {"check": "Existing video generation still works", "critical": True},
            {"check": "Avatar mapping returns valid IDs", "critical": True},
            {"check": "No breaking changes to public APIs", "critical": True},
        ],
    },
]
