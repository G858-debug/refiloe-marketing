#!/usr/bin/env python3
"""Test carousel generation pipeline end-to-end.

This script validates the entire carousel generation flow:
1. Loads configuration
2. Initializes the ContentPipeline
3. Generates educational carousel content
4. Creates carousel slides as images
5. Saves slides to /tmp/test_carousel/

Usage:
    python scripts/test_carousel_generation.py          # Uses AI for content generation
    python scripts/test_carousel_generation.py --mock   # Uses mock content (no API key required)

Requirements:
    - ANTHROPIC_API_KEY environment variable must be set (unless using --mock mode)
    - python-dotenv must be installed (optional)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False
    def load_dotenv(*args, **kwargs):
        pass

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from social_media.carousel_template_generator import CarouselTemplateGenerator


# Constants
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
OUTPUT_DIR = Path("/tmp/test_carousel")
TEST_TOPIC = "How to Automate Client Communication in 5 Steps"
NUM_CONTENT_SLIDES = 3  # Results in 5 total slides (cover + 3 content + CTA)

# Check for mock mode
MOCK_MODE = "--mock" in sys.argv or "-m" in sys.argv


def ensure_env_loaded() -> None:
    """Load environment variables from .env file."""
    dotenv_path = PROJECT_ROOT / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path)
    else:
        load_dotenv()


def check_required_env_vars() -> bool:
    """Check that required environment variables are set."""
    if MOCK_MODE:
        return True  # Skip env check in mock mode

    required_vars = ["ANTHROPIC_API_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print("Please set these in your .env file or environment.")
        print("\nTip: Use --mock flag to run with mock content (no API key required)")
        return False
    return True


def generate_mock_content(topic: str) -> Dict[str, Any]:
    """Generate mock carousel content for testing without API.

    Args:
        topic: Topic for the carousel

    Returns:
        Dict containing mock carousel content structure
    """
    return {
        "title": topic,
        "content": f"Educational carousel about: {topic}",
        "key_points": [
            "Step 1: Set up automated welcome messages for new clients",
            "Step 2: Create follow-up reminder sequences after sessions",
            "Step 3: Use templates for common inquiries and responses",
            "Step 4: Schedule weekly check-in messages automatically",
            "Step 5: Track engagement metrics to optimize timing"
        ],
        "engagement_hook": "Which step will you implement first? Comment below!",
        "hashtags": ["#PersonalTrainer", "#TrainerHacks", "#FitnessBusiness", "#ClientManagement", "#Automation"],
        "tone": "educational",
        "theme": "admin_hacks",
        "format": "carousel_style"
    }


def create_mock_supabase_client() -> Any:
    """Create a mock Supabase client for testing without database.

    Returns a minimal mock that allows ContentGenerator to initialize
    without actual database connectivity.
    """
    class MockTable:
        def select(self, *args, **kwargs):
            return self
        def insert(self, *args, **kwargs):
            return self
        def update(self, *args, **kwargs):
            return self
        def eq(self, *args, **kwargs):
            return self
        def execute(self):
            return type('Response', (), {'data': [], 'error': None})()

    class MockSupabase:
        def table(self, name: str):
            return MockTable()

    return MockSupabase()


def generate_carousel_content(content_generator: ContentGenerator, topic: str, num_slides: int) -> Dict[str, Any]:
    """Generate carousel content using AI.

    Args:
        content_generator: Initialized ContentGenerator instance
        topic: Topic for the carousel
        num_slides: Number of content slides (excluding cover and CTA)

    Returns:
        Dict containing carousel content structure
    """
    print(f"\nGenerating carousel content for: '{topic}'")
    print(f"Requesting {num_slides} content slides...")

    # Use the content generator to create carousel-specific content
    # Generate as a carousel_style format post
    post_data = content_generator.generate_single_post(
        theme="admin_hacks",
        format_type="carousel_style",
        hook_type="quick_win"
    )

    if not post_data:
        print("ERROR: Failed to generate content from AI")
        return {}

    return post_data


def structure_carousel_data(
    content_data: Dict[str, Any],
    topic: str,
    avatar_path: Optional[str] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """Structure generated content into carousel slide format.

    Args:
        content_data: Raw content from AI generator
        topic: Original topic/title
        avatar_path: Optional path to avatar image

    Returns:
        Dict with 'slides' key containing slide configurations
    """
    slides = []

    # Extract key points from content
    key_points = (
        content_data.get("key_points") or
        content_data.get("carousel_slides") or
        content_data.get("tips") or
        []
    )

    # Ensure we have enough points for content slides
    if not key_points:
        # Parse from content text if needed
        content_text = content_data.get("content", "")
        # Create default points from topic
        key_points = [
            "Identify repetitive communication patterns",
            "Set up automated scheduling tools",
            "Create template responses",
            "Implement follow-up reminders",
            "Track client communication metrics"
        ]

    # Ensure we have exactly 5 points for 5-step topic
    while len(key_points) < 5:
        key_points.append(f"Step {len(key_points) + 1}: Additional automation tip")
    key_points = key_points[:5]

    # Slide 1: COVER
    title = content_data.get("title") or topic
    slides.append({
        "type": "COVER",
        "avatar_path": avatar_path or "",
        "title": title
    })

    # Slides 2-4: CONTENT (3 content slides with steps)
    for i, point in enumerate(key_points[:3], 1):
        # Extract step title and bullets
        if isinstance(point, str):
            step_title = f"Step {i}: {point[:50]}..."
            bullets = [point]
        else:
            step_title = f"Step {i}"
            bullets = [str(point)]

        # Add supporting bullets if we have more points
        if i < len(key_points):
            for extra_point in key_points[i:i+2]:
                if isinstance(extra_point, str) and extra_point not in bullets:
                    bullets.append(extra_point[:100])

        slides.append({
            "type": "CONTENT",
            "step_title": step_title,
            "bullets": bullets[:3]  # Max 3 bullets per slide
        })

    # Slide 5: CTA
    cta_headline = content_data.get("engagement_hook") or "Ready to Automate?"
    cta_text = "Save this post for later!"
    cta_subtext = "Follow for more trainer tips"

    slides.append({
        "type": "CTA",
        "headline": cta_headline,
        "cta_text": cta_text,
        "subtext": cta_subtext
    })

    return {"slides": slides}


def create_carousel_slides(
    carousel_generator: CarouselTemplateGenerator,
    carousel_data: Dict[str, List[Dict[str, Any]]],
    output_dir: Path
) -> List[str]:
    """Create carousel slide images.

    Args:
        carousel_generator: Initialized CarouselTemplateGenerator
        carousel_data: Structured carousel data with slides
        output_dir: Directory to save slides

    Returns:
        List of file paths to generated slides
    """
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Override the generator's output directory
    carousel_generator.output_dir = output_dir

    print(f"\nCreating {len(carousel_data.get('slides', []))} carousel slides...")

    slide_paths = carousel_generator.create_carousel(carousel_data)

    return slide_paths


def print_content_structure(content_data: Dict[str, Any], carousel_data: Dict[str, Any]) -> None:
    """Print the generated content structure for inspection.

    Args:
        content_data: Raw AI-generated content
        carousel_data: Structured carousel data
    """
    print("\n" + "=" * 60)
    print("GENERATED CONTENT STRUCTURE")
    print("=" * 60)

    # Title
    print(f"\nTitle: {content_data.get('title', 'N/A')}")

    # Steps/Key Points
    key_points = content_data.get("key_points") or content_data.get("carousel_slides") or []
    print(f"\nKey Points ({len(key_points)} found):")
    for i, point in enumerate(key_points[:5], 1):
        if isinstance(point, str):
            print(f"  {i}. {point[:80]}{'...' if len(point) > 80 else ''}")
        else:
            print(f"  {i}. {point}")

    # CTA
    print(f"\nCTA/Hook: {content_data.get('engagement_hook', 'N/A')}")

    # Hashtags
    hashtags = content_data.get("hashtags", [])
    if hashtags:
        print(f"\nHashtags: {' '.join(hashtags[:5])}")

    # Carousel slide structure
    print("\n" + "-" * 40)
    print("CAROUSEL SLIDE STRUCTURE")
    print("-" * 40)

    for i, slide in enumerate(carousel_data.get("slides", []), 1):
        slide_type = slide.get("type", "UNKNOWN")
        print(f"\nSlide {i} ({slide_type}):")

        if slide_type == "COVER":
            print(f"  Title: {slide.get('title', 'N/A')[:60]}...")
            print(f"  Avatar: {'Set' if slide.get('avatar_path') else 'Not set'}")
        elif slide_type == "CONTENT":
            print(f"  Step: {slide.get('step_title', 'N/A')}")
            bullets = slide.get("bullets", [])
            for bullet in bullets[:3]:
                print(f"    - {bullet[:50]}{'...' if len(bullet) > 50 else ''}")
        elif slide_type == "CTA":
            print(f"  Headline: {slide.get('headline', 'N/A')}")
            print(f"  CTA Text: {slide.get('cta_text', 'N/A')}")
            print(f"  Subtext: {slide.get('subtext', 'N/A')}")


def print_file_paths(slide_paths: List[str]) -> None:
    """Print the generated file paths.

    Args:
        slide_paths: List of file paths to generated slides
    """
    print("\n" + "=" * 60)
    print("GENERATED FILE PATHS")
    print("=" * 60)

    for i, path in enumerate(slide_paths, 1):
        file_path = Path(path)
        exists = file_path.exists()
        size = file_path.stat().st_size if exists else 0
        status = f"({size:,} bytes)" if exists else "(NOT FOUND)"
        print(f"  Slide {i}: {path} {status}")


def main() -> int:
    """Main entry point for carousel generation test."""
    print("=" * 60)
    print("CAROUSEL GENERATION TEST")
    print("=" * 60)
    print(f"Topic: {TEST_TOPIC}")
    print(f"Output Directory: {OUTPUT_DIR}")
    if MOCK_MODE:
        print("Mode: MOCK (using sample content, no API calls)")

    # Load environment
    ensure_env_loaded()

    # Check required environment variables
    if not check_required_env_vars():
        return 1

    # Verify config exists
    if not CONFIG_PATH.exists():
        print(f"ERROR: Configuration file not found: {CONFIG_PATH}")
        return 1

    print(f"\nConfiguration: {CONFIG_PATH}")

    try:
        # Initialize components
        print("\n[1/5] Initializing components...")

        carousel_generator = CarouselTemplateGenerator(
            config_path=str(CONFIG_PATH)
        )
        print("  - CarouselTemplateGenerator initialized")

        content_generator = None
        if not MOCK_MODE:
            # Only initialize content generator if we need AI
            from content_generator import ContentGenerator
            mock_supabase = create_mock_supabase_client()
            content_generator = ContentGenerator(
                config_path=str(CONFIG_PATH),
                supabase_client=mock_supabase
            )
            print("  - ContentGenerator initialized")
        else:
            print("  - ContentGenerator skipped (mock mode)")

        # Generate carousel content
        if MOCK_MODE:
            print("\n[2/5] Using mock carousel content...")
            content_data = generate_mock_content(TEST_TOPIC)
        else:
            print("\n[2/5] Generating carousel content with AI...")
            content_data = generate_carousel_content(
                content_generator=content_generator,
                topic=TEST_TOPIC,
                num_slides=NUM_CONTENT_SLIDES
            )

        if not content_data:
            print("ERROR: Failed to generate content")
            return 1

        print("  - Content generated successfully")

        # Structure the content for carousel
        print("\n[3/5] Structuring carousel data...")
        carousel_data = structure_carousel_data(
            content_data=content_data,
            topic=TEST_TOPIC,
            avatar_path=None  # No avatar for test
        )

        print(f"  - Structured {len(carousel_data.get('slides', []))} slides")

        # Create carousel slides
        print("\n[4/5] Creating carousel slide images...")
        slide_paths = create_carousel_slides(
            carousel_generator=carousel_generator,
            carousel_data=carousel_data,
            output_dir=OUTPUT_DIR
        )

        print(f"  - Generated {len(slide_paths)} slide images")

        # Display results
        print("\n[5/5] Displaying results...")
        print_content_structure(content_data, carousel_data)
        print_file_paths(slide_paths)

        # Summary
        print("\n" + "=" * 60)
        print("TEST COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"Generated {len(slide_paths)} carousel slides")
        print(f"Files saved to: {OUTPUT_DIR}")
        print("\nTo view slides:")
        for path in slide_paths:
            print(f"  open {path}")

        return 0

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
