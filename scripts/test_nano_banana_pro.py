#!/usr/bin/env python3
"""Test script for Leonardo AI Nano Banana Pro image generation.

This script tests the LeonardoGenerator with the Nano Banana Pro model
to generate a single test image of Refiloe in a fitness setting.

Usage:
    python scripts/test_nano_banana_pro.py

Requirements:
    - LEONARDO_API_KEY must be set in environment variables
"""

import os
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from social_media.leonardo_generator import LeonardoGenerator, LeonardoGenerationError


def main():
    """Test Nano Banana Pro image generation."""
    print("=" * 70)
    print("Leonardo AI Nano Banana Pro Test Script")
    print("=" * 70)
    print()

    # Verify API key
    api_key = os.getenv("LEONARDO_API_KEY")
    if not api_key:
        print("❌ ERROR: LEONARDO_API_KEY environment variable not set")
        print()
        print("Please set your Leonardo API key:")
        print("  export LEONARDO_API_KEY='your-api-key-here'")
        sys.exit(1)

    print(f"✓ Leonardo API key found (length: {len(api_key)} characters)")
    print()

    # Test parameters
    prompt = "A confident South African fitness professional in a modern gym setting, wearing athletic clothing, warm smile"
    width = 832
    height = 1024
    num_images = 1
    content_type = "fitness"

    print("Test Parameters:")
    print(f"  Prompt: {prompt}")
    print(f"  Dimensions: {width}x{height}")
    print(f"  Number of images: {num_images}")
    print(f"  Content type: {content_type}")
    print()

    try:
        # Initialize generator
        print("Step 1: Initializing LeonardoGenerator...")
        generator = LeonardoGenerator()
        print("✓ Generator initialized successfully")
        print()

        # Generate image
        print("Step 2: Starting image generation...")
        print("  (This may take 30-60 seconds...)")
        print()

        start_time = time.time()

        result = generator.generate_image(
            prompt=prompt,
            content_type=content_type,
            width=width,
            height=height,
            num_images=num_images,
        )

        end_time = time.time()
        elapsed_time = end_time - start_time

        # Display results
        print("=" * 70)
        print("✓ Image Generation Successful!")
        print("=" * 70)
        print()
        print("Results:")
        print(f"  Generation ID: {result['generation_id']}")
        print(f"  Image URL: {result['image_url']}")
        print(f"  Content Type: {result['content_type']}")
        print(f"  Dimensions: {result['width']}x{result['height']}")
        print(f"  Total Time: {elapsed_time:.2f} seconds")
        print()
        print("Prompt Used:")
        print(f"  {result['prompt'][:200]}...")
        print()
        print("=" * 70)
        print()
        print("🎉 Test completed successfully!")
        print()
        print("You can view the generated image at:")
        print(f"  {result['image_url']}")
        print()

        return 0

    except LeonardoGenerationError as e:
        print()
        print("=" * 70)
        print("❌ Leonardo Generation Error")
        print("=" * 70)
        print()
        print(f"Error: {e}")
        print()
        print("Possible causes:")
        print("  - Invalid API key")
        print("  - API rate limit exceeded")
        print("  - Invalid parameters")
        print("  - Leonardo service issue")
        print()
        return 1

    except Exception as e:
        print()
        print("=" * 70)
        print("❌ Unexpected Error")
        print("=" * 70)
        print()
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {e}")
        print()
        import traceback
        print("Traceback:")
        traceback.print_exc()
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
